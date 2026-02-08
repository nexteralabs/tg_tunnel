"""Business logic for channels"""

import asyncio
import httpx

from ...core.db import get_conn
from ...core.telegram_bot import get_bot_by_token
from ...core.config import settings
from . import models


async def send_to_channel(channel_id: str, text: str) -> None:
    """Send message to channel (bot is looked up internally)"""
    async for conn in get_conn():
        channel = await models.get_channel(conn, channel_id)

    if not channel:
        raise ValueError(f"Channel {channel_id} not registered")

    bot = get_bot_by_token(channel["bot_token"])
    await bot.send_message(chat_id=channel["telegram_chat_id"], text=text)


async def forward_to_callback(channel: dict, message_event: dict) -> bool:
    """
    Forward message to callback with retry logic (matches MVP reference).
    Returns True if successful, False if all retries failed.
    """
    callback_url = channel["callback_url"]
    chat_id = channel["telegram_chat_id"]

    for attempt in range(1, settings.CHANNEL_CALLBACK_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                res = await client.post(callback_url, json=message_event)
                res.raise_for_status()
            return True
        except Exception as e:
            print(f"[Attempt {attempt}] Callback failed for {chat_id}: {e}")
            if attempt < settings.CHANNEL_CALLBACK_MAX_RETRIES:
                await asyncio.sleep(settings.CHANNEL_CALLBACK_RETRY_DELAY)

    # All retries failed - notify channel
    await notify_offline(channel)
    return False


async def notify_offline(channel: dict) -> None:
    """Send offline notification to channel (matches MVP reference)"""
    bot = get_bot_by_token(channel["bot_token"])
    # Send emoji to Telegram (OK), but don't print() emoji (Windows constraint)
    notification_text = f"\u26a0\ufe0f {settings.CHANNEL_OFFLINE_NOTIFICATION}"
    await bot.send_message(chat_id=channel["telegram_chat_id"], text=notification_text)
