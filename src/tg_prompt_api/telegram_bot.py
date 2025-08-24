import re
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

bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
    default=DefaultBotProperties(parse_mode=ParseMode(settings.TELEGRAM_MESSAGE_PARSE_MODE)),
)
dp = Dispatcher()

ID_REPLY_RE = re.compile(r"^ID\s*[:#-]?\s*(#?\w+)\s+(.+)$", re.IGNORECASE)


@dp.message(Command("ping"))
async def ping(m: Message):
    await m.reply("pong")


@dp.message()
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
    media_url: str | None,
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

    if media_url:
        msg = await bot.send_photo(
            chat_id=target_chat_id, photo=media_url, caption=text, reply_markup=kb
        )
    else:
        msg = await bot.send_message(chat_id=target_chat_id, text=text, reply_markup=kb)

    async for aconn in get_conn():
        await set_message_id(aconn, prompt_id, msg.message_id)
        await set_message_map(aconn, prompt_id, msg.message_id)


@dp.callback_query()
async def on_button(cq: CallbackQuery):
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
    
    await bot.send_message(
        chat_id=cq.message.chat.id,
        text=f"{style}: {display_text}",
        parse_mode="Markdown"
    )
    
    # Remove buttons
    try:
        await bot.edit_message_reply_markup(
            chat_id=cq.message.chat.id, message_id=cq.message.message_id, reply_markup=None
        )
    except Exception:
        pass
