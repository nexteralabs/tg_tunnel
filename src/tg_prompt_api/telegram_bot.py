import re
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from .config import settings
from .db import get_conn
from .models import (
    add_option_map,
    set_message_id,
    mark_answered,
    resolve_option_label,
    set_message_map,
    get_prompt,
)
from .util import ulid

# Lazy initialization to avoid conflicts when module is imported multiple times
bot = None
dp = None

def get_bot():
    """Get or create the bot instance."""
    global bot, dp
    if bot is None:
        bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode(settings.TELEGRAM_MESSAGE_PARSE_MODE)),
        )
        dp = Dispatcher()
        
        # Register handlers
        dp.message.register(ping, Command("ping"))
        dp.message.register(on_any_message)
        dp.callback_query.register(on_callback)
    
    return bot, dp


async def manual_polling(bot, dp):
    """Manual polling implementation to avoid aiogram's internal conflicts."""
    offset = 0
    
    while True:
        try:
            updates = await bot.get_updates(
                offset=offset,
                timeout=10,
                allowed_updates=["message", "callback_query"]
            )
            
            for update in updates:
                offset = max(offset, update.update_id + 1)
                # Process update through dispatcher
                await dp.feed_update(bot, update)
                
        except Exception as e:
            print(f"Polling error: {e}")
            await asyncio.sleep(1)

ID_REPLY_RE = re.compile(r"^ID\s*[:#-]?\s*(#?\w+)\s+(.+)$", re.IGNORECASE)


# Handler functions (will be registered in get_bot())
async def ping(m: Message):
    await m.reply("pong")


async def on_any_message(m: Message):
    if not m.text:
        return
    mt = m.text.strip()
    mobj = ID_REPLY_RE.match(mt)
    if not mobj:
        return
    prompt_id, reply_text = mobj.group(1), mobj.group(2)

    async for aconn in get_conn():
        await mark_answered(
            aconn,
            prompt_id,
            answer_type="text",
            value=reply_text,
            user_id=m.from_user.id if m.from_user else None,
            username=m.from_user.username if m.from_user else None,
        )
    await m.reply(f"✅ Recorded answer for ID:{prompt_id}")


async def post_prompt_to_chat(
    prompt_id: str,
    text: str,
    media: str | None,  # Can be URL string, UploadFile, or None
    options: list[str] | None,
    target_chat_id: str | int,
):
    kb = None
    if options:
        rows = []
        for i, label in enumerate(options):
            # Use simple option IDs like "1", "2", etc.
            opt_id = str(i + 1)
            async for aconn in get_conn():
                await add_option_map(aconn, prompt_id, opt_id, label)
            rows.append([InlineKeyboardButton(text=label, callback_data=f"{prompt_id}:{opt_id}")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

    # Use the existing bot instance to avoid session conflicts
    current_bot, _ = get_bot()
    
    try:
        if media:
            # Check if media is an UploadFile object, local file path, or URL string
            from fastapi import UploadFile
            import os
            
            if isinstance(media, UploadFile):
                # Handle uploaded file
                try:
                    # Read file content for sending to Telegram
                    file_content = await media.read()
                    # Reset file position for potential re-reading
                    await media.seek(0)
                    
                    # Send photo with file content
                    from aiogram.types import BufferedInputFile
                    photo = BufferedInputFile(file_content, filename=media.filename or "image.jpg")
                    msg = await current_bot.send_photo(
                        chat_id=target_chat_id, photo=photo, caption=text, reply_markup=kb
                    )
                except Exception as photo_error:
                    # If photo sending fails, fall back to text message
                    print(f"Failed to send uploaded photo {media.filename}: {photo_error}. Falling back to text message.")
                    msg = await current_bot.send_message(
                        chat_id=target_chat_id, 
                        text=f"{text}\n\n[Uploaded file: {media.filename}]", 
                        reply_markup=kb
                    )
            elif isinstance(media, str) and os.path.exists(media) and os.path.isfile(media):
                # Handle local file path
                try:
                    # Read local file content
                    with open(media, 'rb') as f:
                        file_content = f.read()
                    
                    # Send photo with file content
                    from aiogram.types import BufferedInputFile
                    filename = os.path.basename(media)
                    photo = BufferedInputFile(file_content, filename=filename)
                    msg = await current_bot.send_photo(
                        chat_id=target_chat_id, photo=photo, caption=text, reply_markup=kb
                    )
                except Exception as photo_error:
                    # If photo sending fails, fall back to text message
                    print(f"Failed to send local photo {media}: {photo_error}. Falling back to text message.")
                    msg = await current_bot.send_message(
                        chat_id=target_chat_id, 
                        text=f"{text}\n\n[Local file: {media}]", 
                        reply_markup=kb
                    )
            else:
                # Handle URL string (existing logic)
                try:
                    # Try to send as photo first
                    msg = await temp_bot.send_photo(
                        chat_id=target_chat_id, photo=media, caption=text, reply_markup=kb
                    )
                except Exception as photo_error:
                    # If photo sending fails, fall back to text message
                    print(f"Failed to send photo from {media}: {photo_error}. Falling back to text message.")
                    msg = await current_bot.send_message(
                        chat_id=target_chat_id, 
                        text=f"{text}\n\n[Media URL: {media}]", 
                        reply_markup=kb
                    )
        else:
            msg = await current_bot.send_message(chat_id=target_chat_id, text=text, reply_markup=kb)
            
        async for aconn in get_conn():
            await set_message_id(aconn, prompt_id, msg.message_id)
            await set_message_map(aconn, prompt_id, msg.message_id)
    finally:
        # No session cleanup needed - reusing existing bot instance
        pass


# Callback handler (will be registered in get_bot())
async def on_callback(cq: CallbackQuery):
    try:
        pid, oid = cq.data.split(":", 1)
    except Exception:
        return await cq.answer("invalid")

    async for aconn in get_conn():
        label = await resolve_option_label(aconn, pid, oid)
        if not label:
            return await cq.answer("expired")
        
        # Get prompt details for confirmation message
        prompt_data = await get_prompt(aconn, pid)
        prompt_text = prompt_data["text"] if prompt_data else f"prompt {pid}"
        
        await mark_answered(
            aconn,
            pid,
            answer_type="option",
            value=label,
            user_id=cq.from_user.id,
            username=cq.from_user.username,
        )
    
    # Send popup notification
    await cq.answer(f"Selected: {label}")
    
    # Send visible confirmation message with distinct styling
    if label.lower() in ["approve", "approved", "accept", "accepted", "yes"]:
        style = "**✅ Approved**"
    elif label.lower() in ["reject", "rejected", "decline", "declined", "no", "deny", "denied"]:
        style = "**🔴 Rejected**"
    else:
        style = f"**✅ {label.title()}**"
    
    # Truncate prompt text if too long
    display_text = prompt_text[:50] + "..." if len(prompt_text) > 50 else prompt_text
    
    # Get bot instance
    _bot, _ = get_bot()
    
    await _bot.send_message(
        chat_id=cq.message.chat.id,
        text=f"{style}: {display_text}",
        parse_mode="Markdown"
    )
    
    # Remove buttons
    try:
        await _bot.edit_message_reply_markup(
            chat_id=cq.message.chat.id, message_id=cq.message.message_id, reply_markup=None
        )
    except Exception:
        pass
