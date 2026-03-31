"""
Tests for the optional API key authentication middleware.

The middleware is implemented in tg_prompt_api.api.app._check_api_key and is
applied as a dependency on every router.  We exercise it by sending real HTTP
requests through the ASGI app — no mocks on the auth logic itself.
"""
import pytest
from pydantic import SecretStr
from unittest.mock import AsyncMock, patch, MagicMock


def _make_null_conn():
    conn = MagicMock()

    async def _gen():
        yield conn

    return _gen, conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_channels_client(use_auth: bool, api_key: str | None):
    """
    Build a fresh AsyncClient with the given auth settings applied via
    monkeypatching the settings singleton.  Returns the client directly so the
    caller can make requests.
    """
    from tg_prompt_api.core.config import settings
    from httpx import AsyncClient, ASGITransport

    settings.USE_AUTH = use_auth
    settings.API_KEY = SecretStr(api_key) if api_key else None

    fake_get_conn, _ = _make_null_conn()

    with (
        patch("tg_prompt_api.core.db.get_conn", new=fake_get_conn),
        patch(
            "tg_prompt_api.services.channels.poller.restore_all_on_startup",
            new=AsyncMock(),
        ),
        patch(
            "tg_prompt_api.services.channels.models.register_channel",
            new=AsyncMock(),
        ),
        patch(
            "tg_prompt_api.services.prompts.models.clean_on_boot",
            new=AsyncMock(),
        ),
    ):
        from tg_prompt_api.api.app import app

        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthMiddleware:
    async def test_no_auth_any_request_proceeds(self):
        """With USE_AUTH=False, requests without a key should not get 401."""
        from tg_prompt_api.core.config import settings
        from httpx import AsyncClient, ASGITransport
        from pydantic import SecretStr
        from unittest.mock import AsyncMock, patch, MagicMock

        settings.USE_AUTH = False
        settings.API_KEY = None

        fake_get_conn, conn = _make_null_conn()
        # GET /channels lists channels — mock the DB query to return empty list
        conn.cursor.return_value.__aenter__ = AsyncMock(return_value=MagicMock(fetchall=AsyncMock(return_value=[])))

        with (
            patch("tg_prompt_api.core.db.get_conn", new=fake_get_conn),
            patch(
                "tg_prompt_api.services.channels.poller.restore_all_on_startup",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.channels.models.register_channel",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.prompts.models.clean_on_boot",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.channels.models.list_active_channels",
                new=AsyncMock(return_value=[]),
            ),
        ):
            from tg_prompt_api.api.app import app

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/channels")

        assert resp.status_code != 401

    async def test_auth_enabled_no_key_returns_401(self):
        """With USE_AUTH=True, missing X-API-Key header → 401."""
        from tg_prompt_api.core.config import settings
        from httpx import AsyncClient, ASGITransport
        from pydantic import SecretStr

        settings.USE_AUTH = True
        settings.API_KEY = SecretStr("correct-key-here")

        fake_get_conn, _ = _make_null_conn()

        with (
            patch("tg_prompt_api.core.db.get_conn", new=fake_get_conn),
            patch(
                "tg_prompt_api.services.channels.poller.restore_all_on_startup",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.channels.models.register_channel",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.prompts.models.clean_on_boot",
                new=AsyncMock(),
            ),
        ):
            from tg_prompt_api.api.app import app

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/channels")

        assert resp.status_code == 401

    async def test_auth_enabled_wrong_key_returns_401(self):
        """With USE_AUTH=True, incorrect X-API-Key → 401."""
        from tg_prompt_api.core.config import settings
        from httpx import AsyncClient, ASGITransport
        from pydantic import SecretStr

        settings.USE_AUTH = True
        settings.API_KEY = SecretStr("correct-key-here")

        fake_get_conn, _ = _make_null_conn()

        with (
            patch("tg_prompt_api.core.db.get_conn", new=fake_get_conn),
            patch(
                "tg_prompt_api.services.channels.poller.restore_all_on_startup",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.channels.models.register_channel",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.prompts.models.clean_on_boot",
                new=AsyncMock(),
            ),
        ):
            from tg_prompt_api.api.app import app

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/channels", headers={"X-API-Key": "wrong-key"})

        assert resp.status_code == 401

    async def test_auth_enabled_correct_key_proceeds(self):
        """With USE_AUTH=True and correct key, request is not rejected with 401."""
        from tg_prompt_api.core.config import settings
        from httpx import AsyncClient, ASGITransport
        from pydantic import SecretStr

        settings.USE_AUTH = True
        settings.API_KEY = SecretStr("correct-key-here")

        fake_get_conn, _ = _make_null_conn()

        with (
            patch("tg_prompt_api.core.db.get_conn", new=fake_get_conn),
            patch(
                "tg_prompt_api.services.channels.poller.restore_all_on_startup",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.channels.models.register_channel",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.prompts.models.clean_on_boot",
                new=AsyncMock(),
            ),
            patch(
                "tg_prompt_api.services.channels.models.list_active_channels",
                new=AsyncMock(return_value=[]),
            ),
        ):
            from tg_prompt_api.api.app import app

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/channels", headers={"X-API-Key": "correct-key-here"})

        assert resp.status_code != 401
