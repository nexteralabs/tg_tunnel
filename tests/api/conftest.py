"""
API-level fixtures: an AsyncClient wired to the FastAPI app with all real
infrastructure (DB, Telegram, poller) mocked out.
"""
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport


def _make_null_conn():
    """Return an async generator that yields a MagicMock connection (no DB)."""
    conn = MagicMock()
    conn.cursor = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))

    async def _gen():
        yield conn

    return _gen, conn


@pytest.fixture
async def client():
    """
    FastAPI AsyncClient with all external dependencies stubbed out.

    Patches applied:
      - tg_tunnel.core.db.get_conn         → no-op async generator
      - channel poller restore_all_on_startup   → no-op coroutine
      - channel models register_channel         → no-op coroutine
      - prompt models clean_on_boot             → no-op coroutine
      - telegram_bot post_prompt_to_chat        → no-op coroutine (avoids real HTTP)
    """
    fake_get_conn, _conn = _make_null_conn()

    with (
        patch("tg_tunnel.core.db.get_conn", new=fake_get_conn),
        patch(
            "tg_tunnel.services.channels.poller.restore_all_on_startup",
            new=AsyncMock(),
        ),
        patch(
            "tg_tunnel.services.channels.models.register_channel",
            new=AsyncMock(),
        ),
        patch(
            "tg_tunnel.services.prompts.models.clean_on_boot",
            new=AsyncMock(),
        ),
        patch(
            "tg_tunnel.core.telegram_bot.post_prompt_to_chat",
            new=AsyncMock(),
        ),
    ):
        # Import inside the patch block so the app is created with mocked deps
        from tg_tunnel.api.app import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def auth_client(monkeypatch):
    """
    AsyncClient with USE_AUTH=True and API_KEY="test-key-123".
    Uses monkeypatch on the live settings singleton so it is restored automatically.
    """
    from tg_tunnel.core.config import settings
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "USE_AUTH", True)
    monkeypatch.setattr(settings, "API_KEY", SecretStr("test-key-123"))

    fake_get_conn, _conn = _make_null_conn()

    with (
        patch("tg_tunnel.core.db.get_conn", new=fake_get_conn),
        patch(
            "tg_tunnel.services.channels.poller.restore_all_on_startup",
            new=AsyncMock(),
        ),
        patch(
            "tg_tunnel.services.channels.models.register_channel",
            new=AsyncMock(),
        ),
        patch(
            "tg_tunnel.services.prompts.models.clean_on_boot",
            new=AsyncMock(),
        ),
        patch(
            "tg_tunnel.core.telegram_bot.post_prompt_to_chat",
            new=AsyncMock(),
        ),
    ):
        from tg_tunnel.api.app import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
