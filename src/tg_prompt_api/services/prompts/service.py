"""Business logic for prompt domain"""

import os
from ...core.db import get_conn
from . import models


async def create_and_post_prompt(
    chat_id: str | int | None,
    text: str,
    media_path: str | None,
    media_url: str | None,
    options: list[str],
    allow_text: bool,
    callback_url: str | None,
    correlation_id: str | None,
    ttl_sec: int,
    media_file=None,  # Can be UploadFile object
    channel_id: str | None = None,  # NEW parameter
) -> tuple[str, dict]:
    """
    Create prompt in DB and post to Telegram.
    Returns (prompt_id, prompt_row)

    If channel_id provided: uses that channel's bot and chat
    Else: uses __system_prompt__ channel (backward compatible)

    media_file: UploadFile object from FastAPI (takes precedence over media_path/media_url)
    """
    from ...core.telegram_bot import post_prompt_to_chat
    from ..channels import models as channel_models

    # Validate that only one media source is provided
    has_media_url = bool(media_url and str(media_url).strip())
    has_media_path = bool(media_path and media_path.strip())
    has_media_file = bool(media_file)

    media_count = sum([has_media_url, has_media_path, has_media_file])
    if media_count > 1:
        raise ValueError("Cannot provide multiple media sources")

    # Resolve channel (default to __system_prompt__)
    resolved_channel_id = channel_id or "__system_prompt__"

    # Look up channel to get bot token and chat ID
    async for conn in get_conn():
        channel = await channel_models.get_channel(conn, resolved_channel_id)

    if not channel:
        raise ValueError(f"Channel {resolved_channel_id} not found")

    # Use channel's chat (ignore legacy chat_id parameter if channel_id provided)
    target_chat = channel["telegram_chat_id"]
    bot_token = channel["bot_token"]

    # Determine what to pass to telegram
    media_to_send = None
    if has_media_file:
        media_to_send = media_file  # Pass UploadFile directly
    elif has_media_url:
        media_to_send = str(media_url)
    elif has_media_path:
        # Validate file exists
        if not os.path.exists(media_path):
            raise FileNotFoundError(f"File not found: {media_path}")
        if not os.path.isfile(media_path):
            raise ValueError(f"Path is not a file: {media_path}")
        media_to_send = media_path

    # Create prompt in database
    async for aconn in get_conn():
        prompt_id = await models.create_prompt(
            aconn,
            chat_id=str(target_chat),
            text=text,
            media_url=str(media_url) if media_url else media_path,
            options=options,
            allow_text=allow_text,
            callback_url=str(callback_url) if callback_url else None,
            correlation_id=correlation_id,
            ttl_sec=ttl_sec,
        )

    # Post to Telegram using channel's bot
    await post_prompt_to_chat(prompt_id, text, media_to_send, options, target_chat, bot_token)

    # Fetch created prompt
    async for aconn in get_conn():
        row = await models.get_prompt(aconn, prompt_id)
        if not row:
            raise RuntimeError("Prompt missing after create")

    return prompt_id, row
