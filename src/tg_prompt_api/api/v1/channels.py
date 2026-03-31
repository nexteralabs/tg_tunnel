"""Channel API endpoints (matches MVP reference exactly)"""

from fastapi import APIRouter, HTTPException

from ...core.db import get_conn
from ...services.channels import models, schemas, service, poller

router = APIRouter()


@router.post("/register-channel")  # Exact match from MVP reference
async def register_channel(data: schemas.ChannelRegisterIn):
    """Register channel and start polling (idempotent)"""
    # Validate: MESSAGE channels must have callback_url
    if data.channel_type == "MESSAGE" and not data.callback_url:
        raise HTTPException(400, "MESSAGE channels require callback_url")

    existing = None
    # Check if channel already exists and is active
    async for conn in get_conn():
        existing = await models.get_channel(conn, data.channel_id)
        if existing and existing["is_active"]:
            # Channel already registered - this is idempotent behavior
            # Just ensure config is up to date
            await models.register_channel(
                conn,
                data.channel_id,
                data.telegram_chat_id,
                data.bot_token,
                data.callback_url,
                data.channel_type,
            )
            return {"status": f"Channel {data.channel_id} already registered (config updated)."}

        # New registration
        await models.register_channel(
            conn,
            data.channel_id,
            data.telegram_chat_id,
            data.bot_token,
            data.callback_url,
            data.channel_type,
        )

    # Start polling immediately
    await poller.start_polling(data.channel_id)

    return {"status": f"Channel {data.channel_id} registered."}


@router.post("/send")  # Exact match from MVP reference
async def send_message(data: schemas.ChannelSendIn):
    """Send message via channel's bot"""
    try:
        await service.send_to_channel(data.channel_id, data.text)
        return {"status": "sent"}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/channels")  # Exact match from MVP reference
async def list_channels():
    """List active channels"""
    channels: list[dict] = []
    async for conn in get_conn():
        channels = await models.list_active_channels(conn)

    return [
        {"channel_id": ch["channel_id"], "telegram_chat_id": ch["telegram_chat_id"]}
        for ch in channels
    ]


@router.delete("/channels/{channel_id}")  # Exact match from MVP reference
async def unregister_channel(channel_id: str):
    """Stop polling and deactivate channel"""
    channel = None
    async for conn in get_conn():
        channel = await models.get_channel(conn, channel_id)

    if not channel:
        raise HTTPException(404, f"Channel {channel_id} not found.")

    # Stop polling
    await poller.stop_polling(channel_id)

    # Deactivate in DB
    async for conn in get_conn():
        await models.deactivate_channel(conn, channel_id)

    return {"status": f"Channel {channel_id} unregistered."}
