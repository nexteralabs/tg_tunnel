"""Telegram handlers for prompt domain"""

import re
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from ...core.db import get_conn
from . import models

router = Router()

ID_REPLY_RE = re.compile(r"^ID\s*[:#-]?\s*(#?\w+)\s+(.+)$", re.IGNORECASE)


@router.message(Command("ping"))
async def ping_handler(m: Message):
    """Health check command"""
    await m.reply("pong")


@router.message()
async def text_response_handler(m: Message):
    """Handle text responses like 'ID:#123 my answer'"""
    if not m.text:
        return

    mt = m.text.strip()
    mobj = ID_REPLY_RE.match(mt)
    if not mobj:
        return

    prompt_id, reply_text = mobj.group(1), mobj.group(2)

    async for aconn in get_conn():
        await models.mark_answered(
            aconn,
            prompt_id,
            answer_type="text",
            value=reply_text,
            user_id=m.from_user.id if m.from_user else None,
            username=m.from_user.username if m.from_user else None,
        )
    await m.reply(f"Recorded answer for ID:{prompt_id}")  # No emoji for Windows


@router.callback_query()
async def button_response_handler(cq: CallbackQuery):
    """Handle button clicks on prompts"""
    try:
        pid, oid = cq.data.split(":", 1)
    except Exception:
        return await cq.answer("invalid")

    async for aconn in get_conn():
        label = await models.resolve_option_label(aconn, pid, oid)
        if not label:
            return await cq.answer("expired")

        # Get prompt details for confirmation message
        prompt_data = await models.get_prompt(aconn, pid)
        prompt_text = prompt_data["text"] if prompt_data else f"prompt {pid}"

        await models.mark_answered(
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
        style = "**Approved**"  # No emoji for Windows
    elif label.lower() in ["reject", "rejected", "decline", "declined", "no", "deny", "denied"]:
        style = "**Rejected**"  # No emoji for Windows
    else:
        style = f"**{label.title()}**"

    # Truncate prompt text if too long
    display_text = prompt_text[:50] + "..." if len(prompt_text) > 50 else prompt_text

    # Get bot instance
    from ...core.telegram_bot import get_bot

    _bot, _ = get_bot()

    await _bot.send_message(
        chat_id=cq.message.chat.id, text=f"{style}: {display_text}", parse_mode="Markdown"
    )

    # Remove buttons
    try:
        await _bot.edit_message_reply_markup(
            chat_id=cq.message.chat.id, message_id=cq.message.message_id, reply_markup=None
        )
    except Exception:
        pass
