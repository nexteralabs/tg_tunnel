"""FastAPI application factory"""

import os
import asyncio
from fastapi import FastAPI

from ..core.config import settings
from ..core.security import setup_secure_logging
from ..core.db import get_conn
from ..services.prompts import models as prompt_models
from ..services.channels import poller as channel_poller
from .v1 import prompts, channels

# Fix Windows event loop policy for psycopg
if os.name == "nt":  # Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Telegram Prompt & Channel Gateway")

    # Register routers
    app.include_router(prompts.router, prefix="/v1")
    app.include_router(channels.router)  # No prefix - matches MVP reference

    @app.on_event("startup")
    async def startup():
        """Application startup: setup logging, clean boot, and restore channel polling."""
        # Setup secure logging with token redaction
        setup_secure_logging()

        # Auto-register the default prompt channel
        from ..services.channels import models as channel_models

        async for conn in get_conn():
            await channel_models.register_channel(
                conn,
                channel_id="__system_prompt__",
                telegram_chat_id=settings.TELEGRAM_TARGET_CHAT_ID,
                bot_token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
                callback_url=None,  # PROMPT channels use per-prompt callbacks
                channel_type="PROMPT",
            )

        # Clean on boot if enabled
        if settings.CLEAN_ON_BOOT:
            async for aconn in get_conn():
                await prompt_models.clean_on_boot(aconn)

        # Restore channel polling for all active channels (including default)
        await channel_poller.restore_all_on_startup()

    return app


# Create the app instance
app = create_app()
