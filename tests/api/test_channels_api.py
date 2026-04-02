"""
Tests for the channel REST endpoints (/register-channel, /send, /channels, /channels/{id}).

Uses the `client` fixture from tests/api/conftest.py which patches get_conn to a no-op.
Individual tests additionally patch model/service functions so their behaviour is
fully controlled — no real DB or Telegram calls are made.
"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def reset_use_auth():
    """Ensure USE_AUTH is False before each test in this module.

    test_auth.py mutates the settings singleton directly. This fixture prevents
    that pollution from causing 401 responses on unrelated channel endpoint tests.
    """
    from tg_gateway.core.config import settings
    settings.USE_AUTH = False
    yield
    settings.USE_AUTH = False


class TestRegisterChannel:
    async def test_message_channel_without_callback_url_returns_400(self, client):
        """MESSAGE channels require callback_url — missing it must return 400 before any DB call."""
        resp = await client.post(
            "/register-channel",
            json={
                "channel_id": "test-ch",
                "telegram_chat_id": "-1001234567890",
                "bot_token": "111111111:AABBCCDDEEFFaabbccddeeff-testtoken",
                "channel_type": "MESSAGE",
                # callback_url intentionally omitted
            },
        )
        assert resp.status_code == 400
        assert "callback_url" in resp.text.lower() or "callback" in resp.text.lower()

    async def test_prompt_channel_without_callback_url_succeeds(self, client):
        """PROMPT channels do not require callback_url — registration must succeed."""
        with (
            patch(
                "tg_gateway.services.channels.models.get_channel",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "tg_gateway.services.channels.models.register_channel",
                new=AsyncMock(),
            ),
            patch(
                "tg_gateway.services.channels.poller.start_polling",
                new=AsyncMock(),
            ),
        ):
            resp = await client.post(
                "/register-channel",
                json={
                    "channel_id": "prompt-ch",
                    "telegram_chat_id": "-1001234567890",
                    "bot_token": "111111111:AABBCCDDEEFFaabbccddeeff-testtoken",
                    "channel_type": "PROMPT",
                    # No callback_url — allowed for PROMPT
                },
            )
        assert resp.status_code == 200
        assert "registered" in resp.json()["status"]

    async def test_register_channel_returns_registered_status(self, client):
        """Happy path: new channel is stored and polling starts, response confirms registration."""
        with (
            patch(
                "tg_gateway.services.channels.models.get_channel",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "tg_gateway.services.channels.models.register_channel",
                new=AsyncMock(),
            ),
            patch(
                "tg_gateway.services.channels.poller.start_polling",
                new=AsyncMock(),
            ),
        ):
            resp = await client.post(
                "/register-channel",
                json={
                    "channel_id": "my-channel",
                    "telegram_chat_id": "-1001234567890",
                    "bot_token": "111111111:AABBCCDDEEFFaabbccddeeff-testtoken",
                    "callback_url": "http://myapp.example.com/cb",
                    "channel_type": "MESSAGE",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "my-channel" in data["status"]
        assert "registered" in data["status"].lower()


class TestSendMessage:
    async def test_send_to_unknown_channel_returns_404(self, client):
        """When send_to_channel raises ValueError (channel not found), the API returns 404."""
        with patch(
            "tg_gateway.services.channels.service.send_to_channel",
            new=AsyncMock(side_effect=ValueError("Channel unknown-ch not registered")),
        ):
            resp = await client.post(
                "/send",
                json={"channel_id": "unknown-ch", "text": "hello"},
            )
        assert resp.status_code == 404

    async def test_send_to_known_channel_returns_sent(self, client):
        """Successful send returns {"status": "sent"}."""
        with patch(
            "tg_gateway.services.channels.service.send_to_channel",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.post(
                "/send",
                json={"channel_id": "my-channel", "text": "hello world"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"status": "sent"}


class TestListChannels:
    async def test_list_channels_returns_list(self, client):
        """GET /channels returns a list (possibly empty or with items)."""
        fake_channels = [
            {
                "channel_id": "ch-1",
                "telegram_chat_id": "-100111",
                "bot_token": "secret-token-1",
                "is_active": True,
                "last_update_id": 0,
                "callback_url": None,
                "channel_type": "MESSAGE",
            },
            {
                "channel_id": "ch-2",
                "telegram_chat_id": "-100222",
                "bot_token": "secret-token-2",
                "is_active": True,
                "last_update_id": 5,
                "callback_url": "http://cb.example.com",
                "channel_type": "MESSAGE",
            },
        ]
        with patch(
            "tg_gateway.services.channels.models.list_active_channels",
            new=AsyncMock(return_value=fake_channels),
        ):
            resp = await client.get("/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_list_channels_returns_only_id_and_chat_id(self, client):
        """Regression: bot_token must NOT appear in the /channels response (security)."""
        fake_channels = [
            {
                "channel_id": "ch-secret",
                "telegram_chat_id": "-100999",
                "bot_token": "SUPER_SECRET_TOKEN",
                "is_active": True,
                "last_update_id": 0,
                "callback_url": None,
                "channel_type": "MESSAGE",
            },
        ]
        with patch(
            "tg_gateway.services.channels.models.list_active_channels",
            new=AsyncMock(return_value=fake_channels),
        ):
            resp = await client.get("/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        item = data[0]
        # Only these two keys should be present
        assert "channel_id" in item
        assert "telegram_chat_id" in item
        # Token must never leak
        assert "bot_token" not in item
        assert "SUPER_SECRET_TOKEN" not in resp.text


class TestDeleteChannel:
    async def test_delete_channel_not_found_returns_404(self, client):
        """Regression: DELETE /channels/{id} when channel doesn't exist must return 404, not 200."""
        with patch(
            "tg_gateway.services.channels.models.get_channel",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.delete("/channels/nonexistent-ch")
        assert resp.status_code == 404

    async def test_delete_channel_succeeds_returns_200(self, client):
        """When channel exists, stop_polling is called and deactivate is applied; returns 200."""
        fake_channel = {
            "channel_id": "my-channel",
            "telegram_chat_id": "-100111",
            "bot_token": "token",
            "is_active": True,
        }
        with (
            patch(
                "tg_gateway.services.channels.models.get_channel",
                new=AsyncMock(return_value=fake_channel),
            ),
            patch(
                "tg_gateway.services.channels.poller.stop_polling",
                new=AsyncMock(),
            ),
            patch(
                "tg_gateway.services.channels.models.deactivate_channel",
                new=AsyncMock(),
            ),
        ):
            resp = await client.delete("/channels/my-channel")
        assert resp.status_code == 200
        assert "my-channel" in resp.json()["status"]
