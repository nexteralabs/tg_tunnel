"""Channel polling management (matches MVP reference architecture)"""

import asyncio
import logging

from ...core.db import get_conn
from ...core.telegram_bot import get_bot_by_token
from ...core.notifier import schedule_callback
from . import models, service

logger = logging.getLogger(__name__)

# Track polling tasks
_polling_tasks: dict[str, asyncio.Task] = {}


async def start_polling(channel_id: str) -> None:
    """Start polling for a channel (idempotent - cancels existing task)"""
    # Cancel existing task if running
    if channel_id in _polling_tasks:
        _polling_tasks[channel_id].cancel()
        try:
            await _polling_tasks[channel_id]
        except asyncio.CancelledError:
            pass

    # Start new polling task
    task = asyncio.create_task(_poll_loop(channel_id))
    _polling_tasks[channel_id] = task
    logger.info("Polling started for channel %s", channel_id)


async def stop_polling(channel_id: str) -> None:
    """Stop polling for a channel"""
    if channel_id in _polling_tasks:
        _polling_tasks[channel_id].cancel()
        try:
            await _polling_tasks[channel_id]
        except asyncio.CancelledError:
            pass
        del _polling_tasks[channel_id]
        logger.info("Polling stopped for channel %s", channel_id)


async def restore_all_on_startup() -> None:
    """Restore polling for all active channels on app startup"""
    channels: list[dict] = []
    try:
        async for conn in get_conn():
            channels = await models.list_active_channels(conn)
    except Exception as exc:
        logger.error("Failed to restore channels on startup: %s", exc)
        return

    for channel in channels:
        await start_polling(channel["channel_id"])

    logger.info("Restored polling for %d channels", len(channels))


async def _poll_loop(channel_id: str) -> None:
    """Continuous polling loop for one channel (handles PROMPT and MESSAGE types)"""
    async for conn in get_conn():
        channel = await models.get_channel(conn, channel_id)

    if not channel or not channel["is_active"]:
        return

    bot = get_bot_by_token(channel["bot_token"])
    offset = channel["last_update_id"]
    chat_id = channel["telegram_chat_id"]
    channel_type = channel.get("channel_type", "MESSAGE")

    # Polling loop: while channel exists in DB as active
    while True:
        try:
            # Check if channel still active
            async for conn in get_conn():
                channel = await models.get_channel(conn, channel_id)

            if not channel or not channel["is_active"]:
                logger.info("Channel %s deactivated, stopping poll", channel_id)
                break

            # Get updates from Telegram (include callback_query for buttons)
            updates = await bot.get_updates(
                offset=offset + 1, timeout=30, allowed_updates=["message", "callback_query"]
            )

            if updates:
                logger.debug("Channel %s received %d updates", channel_id, len(updates))

            for update in updates:
                offset = update.update_id

                # Log update type
                update_type = "unknown"
                if update.callback_query:
                    update_type = "callback_query"
                elif update.message:
                    update_type = "message"
                logger.debug("Channel %s processing update type: %s", channel_id, update_type)

                # Update offset in DB
                async for conn in get_conn():
                    await models.update_last_update_id(conn, channel_id, offset)

                # Handle button callbacks (same for all channel types)
                if update.callback_query:
                    logger.debug("Handling button callback for channel %s", channel_id)
                    await _handle_button_callback(update.callback_query, bot)

                # Handle messages (different behavior based on channel type)
                elif update.message:
                    msg = update.message

                    if channel_type == "MESSAGE":
                        # MESSAGE channels: Forward to app callback
                        from_user = "unknown"
                        if msg.from_user:
                            from_user = (
                                msg.from_user.username
                                or msg.from_user.first_name
                                or f"user_{msg.from_user.id}"
                            )

                        message_event = {
                            "type": "telegram.message.created",
                            "channel_id": channel_id,
                            "telegram_chat_id": chat_id,
                            "from": from_user,
                            "text": msg.text or "",
                        }

                        await service.forward_to_callback(channel, message_event)

                    elif channel_type == "PROMPT":
                        # PROMPT channels: Check for text response pattern (ID:#123 response)
                        await _handle_text_response(msg, bot)

        except Exception as exc:
            logger.warning("Polling error for channel %s: %s", channel_id, exc)
            await asyncio.sleep(5)


async def _handle_button_callback(callback_query, bot):
    """Handle button clicks for any channel (unified handler)"""
    from ...services.prompts import models as prompt_models

    try:
        prompt_id, option_id = callback_query.data.split(":", 1)
    except Exception:
        await callback_query.answer("invalid")
        return

    async for conn in get_conn():
        # Look up option label
        label = await prompt_models.resolve_option_label(conn, prompt_id, option_id)
        if not label:
            await callback_query.answer("expired")
            return

        # Get prompt details for confirmation
        prompt_data = await prompt_models.get_prompt(conn, prompt_id)

        logger.info("Prompt %s answered with option: %s", prompt_id, label)

        # Mark as answered and schedule callback if applicable
        callback_info = await prompt_models.mark_answered(
            conn,
            prompt_id,
            answer_type="option",
            value=label,
            user_id=callback_query.from_user.id,
            username=callback_query.from_user.username,
        )
        if callback_info:
            schedule_callback(callback_info["callback_url"], callback_info["payload"])

    # Send popup notification (small notification at top of Telegram)
    await callback_query.answer(f"Selected: {label}")

    # Remove buttons
    try:
        await bot.edit_message_reply_markup(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=None,
        )
    except Exception:
        pass


async def _handle_text_response(message, bot):
    """Handle text responses (ID:#123 answer) for PROMPT channels"""
    from ...services.prompts import models as prompt_models
    import re

    if not message.text:
        return

    # Check for ID:#123 pattern
    ID_REPLY_RE = re.compile(r"^ID\s*[:#-]?\s*(#?\w+)\s+(.+)$", re.IGNORECASE)
    match = ID_REPLY_RE.match(message.text.strip())

    if not match:
        return

    prompt_id, reply_text = match.group(1), match.group(2)

    # Mark as answered and schedule callback if applicable
    async for conn in get_conn():
        callback_info = await prompt_models.mark_answered(
            conn,
            prompt_id,
            answer_type="text",
            value=reply_text,
            user_id=message.from_user.id if message.from_user else None,
            username=message.from_user.username if message.from_user else None,
        )
        if callback_info:
            schedule_callback(callback_info["callback_url"], callback_info["payload"])

    # Send confirmation
    await message.reply(f"Recorded answer for ID:{prompt_id}")
