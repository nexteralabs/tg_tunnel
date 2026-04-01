"""Database operations for channels"""

from ...core.db import fetchone, fetchall, execute


async def register_channel(
    conn,
    channel_id: str,
    telegram_chat_id: str,
    bot_token: str,
    callback_url: str | None,
    channel_type: str = "MESSAGE",
) -> None:
    """Register or update channel (idempotent)"""
    await execute(
        conn,
        """
        INSERT INTO channels (channel_id, telegram_chat_id, bot_token, callback_url, channel_type)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (channel_id)
        DO UPDATE SET
            telegram_chat_id = EXCLUDED.telegram_chat_id,
            bot_token = EXCLUDED.bot_token,
            callback_url = EXCLUDED.callback_url,
            channel_type = EXCLUDED.channel_type,
            last_update_id = COALESCE(channels.last_update_id, 0),
            is_active = true
        """,
        channel_id,
        telegram_chat_id,
        bot_token,
        callback_url,
        channel_type,
    )


async def get_channel(conn, channel_id: str) -> dict | None:
    """Get channel by ID"""
    return await fetchone(conn, "SELECT * FROM channels WHERE channel_id = %s", channel_id)


async def list_active_channels(conn) -> list[dict]:
    """List all active channels"""
    return await fetchall(
        conn,
        "SELECT * FROM channels WHERE is_active = true",
    )


async def update_last_update_id(conn, channel_id: str, update_id: int) -> None:
    """Update polling offset"""
    await execute(
        conn,
        "UPDATE channels SET last_update_id = %s WHERE channel_id = %s",
        update_id,
        channel_id,
    )


async def deactivate_channel(conn, channel_id: str) -> None:
    """Deactivate channel (soft delete)"""
    await execute(conn, "UPDATE channels SET is_active = false WHERE channel_id = %s", channel_id)
