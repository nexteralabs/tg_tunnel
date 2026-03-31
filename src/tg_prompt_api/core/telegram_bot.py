import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings
from .db import get_conn

# Lazy initialization to avoid conflicts when module is imported multiple times
bot = None
dp = None
_bots = {}  # Cache for multiple bot instances (for channels)


def get_bot():
    """Get or create the default bot instance for prompts."""
    global bot, dp
    if bot is None:
        bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
            default=DefaultBotProperties(
                parse_mode=ParseMode(settings.TELEGRAM_MESSAGE_PARSE_MODE)
            ),
        )
        dp = Dispatcher()

        # Register prompt handlers
        from ..services.prompts.handlers import router as prompt_router

        dp.include_router(prompt_router)

    return bot, dp


def get_bot_by_token(token: str) -> Bot:
    """Get or create bot for any token (for channels)."""
    if token not in _bots:
        _bots[token] = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return _bots[token]


async def release_bot(token: str) -> None:
    """Remove a bot from the cache, closing its session if open."""
    if token in _bots:
        cached = _bots[token]
        try:
            await cached.session.close()
        except Exception:
            pass
        del _bots[token]


async def post_prompt_to_chat(
    prompt_id: str,
    text: str,
    media: str | None,  # Can be URL string, UploadFile, or None
    options: list[str] | None,
    target_chat_id: str | int,
    bot_token: str | None = None,  # NEW parameter - defaults to config token
):
    """Post prompt to Telegram chat with optional buttons and media."""
    from ..services.prompts import models as prompt_models

    kb = None
    if options:
        rows = []
        async for aconn in get_conn():
            for i, label in enumerate(options):
                # Use simple option IDs like "1", "2", etc.
                opt_id = str(i + 1)
                await prompt_models.add_option_map(aconn, prompt_id, opt_id, label)
                rows.append(
                    [InlineKeyboardButton(text=label, callback_data=f"{prompt_id}:{opt_id}")]
                )
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

    # Use specified bot token or default bot
    if bot_token:
        current_bot = get_bot_by_token(bot_token)
    else:
        current_bot, _ = get_bot()

    # Pre-read media bytes before passing to the retry function
    media_to_send: str | bytes | None
    if media is not None:
        from fastapi import UploadFile
        import os

        if isinstance(media, UploadFile):
            media_to_send = await media.read()
        elif isinstance(media, str) and os.path.exists(media) and os.path.isfile(media):
            media_to_send = await asyncio.to_thread(lambda: open(media, "rb").read())
        else:
            # URL string — pass as-is
            media_to_send = media
    else:
        media_to_send = None

    # Send message with retry logic
    msg = await _send_telegram_message_with_retry(
        current_bot, target_chat_id, text, media_to_send, kb
    )

    async for aconn in get_conn():
        await prompt_models.set_message_id(aconn, prompt_id, msg.message_id)
        await prompt_models.set_message_map(aconn, prompt_id, msg.message_id)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def _send_telegram_message_with_retry(
    bot, target_chat_id, text, media: str | bytes | None, kb
):
    """
    Send message to Telegram with retry logic.

    WARNING: Retries can cause duplicate messages if the send succeeds but the response times out.
    Reduced to 3 attempts to minimize duplicates during network issues.

    media must be pre-read bytes, a URL string, or None. UploadFile objects must be
    read before calling this function to avoid EOF on retry attempts.
    """
    if media is not None:
        if isinstance(media, bytes):
            from aiogram.types import BufferedInputFile

            photo = BufferedInputFile(media, filename="image.jpg")
            return await bot.send_photo(
                chat_id=target_chat_id, photo=photo, caption=text, reply_markup=kb
            )
        else:
            # URL string
            return await bot.send_photo(
                chat_id=target_chat_id, photo=media, caption=text, reply_markup=kb
            )
    else:
        return await bot.send_message(chat_id=target_chat_id, text=text, reply_markup=kb)
