"""FastAPI application factory"""

import hmac
import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException

from ..core.config import settings
from ..core.security import setup_secure_logging
from ..core.db import get_conn
from ..services.prompts import models as prompt_models
from ..services.channels import poller as channel_poller
from .v1 import prompts, channels

logger = logging.getLogger(__name__)


async def _check_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Validate API key when USE_AUTH is enabled."""
    if not settings.USE_AUTH:
        return
    if x_api_key is None or not hmac.compare_digest(x_api_key, settings.API_KEY.get_secret_value()):
        raise HTTPException(401, "Invalid or missing API key")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Application startup: setup logging, clean boot, and restore channel polling."""
    setup_secure_logging()

    from ..services.channels import models as channel_models

    try:
        async for conn in get_conn():
            await channel_models.register_channel(
                conn,
                channel_id="__system_prompt__",
                telegram_chat_id=settings.TELEGRAM_TARGET_CHAT_ID,
                bot_token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
                callback_url=None,
                channel_type="PROMPT",
            )
    except Exception as exc:
        logger.error("Failed to register __system_prompt__ channel on startup: %s", exc)

    if settings.CLEAN_ON_BOOT:
        try:
            async for aconn in get_conn():
                await prompt_models.clean_on_boot(aconn)
        except Exception as exc:
            logger.error("Failed to clean prompts on boot: %s", exc)

    await channel_poller.restore_all_on_startup()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Telegram Prompt & Channel Gateway", lifespan=_lifespan)

    app.include_router(prompts.router, prefix="/v1", dependencies=[Depends(_check_api_key)])
    app.include_router(channels.router, dependencies=[Depends(_check_api_key)])

    return app


# Create the app instance
app = create_app()
