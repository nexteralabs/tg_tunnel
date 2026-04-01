"""
Tests for the prompts REST endpoints (POST /v1/prompts, GET /v1/prompts/pending,
GET /v1/prompts/{prompt_id}).

Uses the `client` fixture from tests/api/conftest.py.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_use_auth():
    """Ensure USE_AUTH is False before each test in this module.

    test_auth.py mutates the settings singleton directly. This fixture prevents
    that pollution from causing 401 responses on unrelated prompt endpoint tests.
    """
    from tg_tunnel.core.config import settings
    settings.USE_AUTH = False
    yield
    settings.USE_AUTH = False


# ---------------------------------------------------------------------------
# Minimal valid payload for POST /v1/prompts
# ---------------------------------------------------------------------------
_BASE_PROMPT = {
    "text": "Do you approve?",
    "options": ["Yes", "No"],
}


class TestCreatePrompt:
    async def test_create_prompt_requires_text(self, client):
        """Missing 'text' field → 422 Unprocessable Entity (Pydantic validation)."""
        resp = await client.post(
            "/v1/prompts",
            json={"options": ["Yes", "No"]},
        )
        assert resp.status_code == 422

    async def test_create_prompt_rejects_multiple_media_sources(self, client):
        """Providing both media_url and media_path raises ValueError → 400."""
        payload = {
            **_BASE_PROMPT,
            "media_url": "https://example.com/image.jpg",
            "media_path": "/data/media/image.jpg",
        }
        with patch(
            "tg_tunnel.services.prompts.service.create_and_post_prompt",
            new=AsyncMock(side_effect=ValueError("Cannot provide multiple media sources")),
        ):
            resp = await client.post("/v1/prompts", json=payload)
        assert resp.status_code == 400
        assert "media" in resp.text.lower() or "multiple" in resp.text.lower()

    async def test_create_prompt_invalid_media_path_returns_400(self, client):
        """media_path with MEDIA_ALLOWED_DIR unset raises ValueError → 400."""
        payload = {
            **_BASE_PROMPT,
            "media_path": "/some/path.jpg",
        }
        with patch(
            "tg_tunnel.services.prompts.service.create_and_post_prompt",
            new=AsyncMock(side_effect=ValueError("Invalid media path")),
        ):
            resp = await client.post("/v1/prompts", json=payload)
        assert resp.status_code == 400

    async def test_create_prompt_succeeds_returns_prompt_id(self, client):
        """Happy path: service returns (#1, row) → response contains prompt_id."""
        fake_row = {
            "chat_id": "-100123",
            "message_id": 42,
        }
        with patch(
            "tg_tunnel.services.prompts.service.create_and_post_prompt",
            new=AsyncMock(return_value=("#1", fake_row)),
        ):
            resp = await client.post("/v1/prompts", json=_BASE_PROMPT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["prompt_id"] == "#1"
        assert data["chat_id"] == "-100123"
        assert data["message_id"] == 42

    async def test_create_prompt_file_not_found_returns_generic_error(self, client):
        """FileNotFoundError must produce a generic error response — no filesystem path leaked."""
        with patch(
            "tg_tunnel.services.prompts.service.create_and_post_prompt",
            new=AsyncMock(side_effect=FileNotFoundError("/data/media/missing.jpg")),
        ):
            resp = await client.post(
                "/v1/prompts",
                json={**_BASE_PROMPT, "media_path": "/data/media/missing.jpg"},
            )
        assert resp.status_code == 400
        body = resp.json()
        # Error response must use the generic shape, not expose the real path
        detail = body.get("detail") if isinstance(body, dict) else body
        if isinstance(detail, dict):
            assert detail.get("error") == "file_not_found"
        # Real filesystem path must not be present in the response
        assert "/data/media/missing.jpg" not in resp.text


class TestListPendingPrompts:
    async def test_list_pending_returns_empty_list(self, client):
        """GET /v1/prompts/pending returns [] when no pending prompts exist."""
        with patch(
            "tg_tunnel.services.prompts.models.list_pending",
            new=AsyncMock(return_value=[]),
        ):
            resp = await client.get("/v1/prompts/pending")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_pending_returns_prompts(self, client):
        """GET /v1/prompts/pending returns all pending prompt rows."""
        now = datetime.now(timezone.utc)
        fake_rows = [
            {
                "id": "uuid-1",
                "chat_id": "-100111",
                "message_id": 10,
                "text": "Approve deployment?",
                "state": "PENDING",
                "created_at": now,
                "expires_at": None,
                "answer": None,
            },
            {
                "id": "uuid-2",
                "chat_id": "-100222",
                "message_id": 11,
                "text": "Scale down cluster?",
                "state": "PENDING",
                "created_at": now,
                "expires_at": None,
                "answer": None,
            },
        ]
        with patch(
            "tg_tunnel.services.prompts.models.list_pending",
            new=AsyncMock(return_value=fake_rows),
        ):
            resp = await client.get("/v1/prompts/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "uuid-1"
        assert data[1]["id"] == "uuid-2"


class TestGetPrompt:
    async def test_get_prompt_not_found_returns_404(self, client):
        """GET /v1/prompts/#999 when prompt does not exist returns 404."""
        with patch(
            "tg_tunnel.services.prompts.models.get_prompt",
            new=AsyncMock(return_value=None),
        ):
            resp = await client.get("/v1/prompts/%23999")
        assert resp.status_code == 404

    async def test_get_prompt_returns_prompt_row(self, client):
        """GET /v1/prompts/#1 with an existing prompt returns the prompt data."""
        now = datetime.now(timezone.utc)
        fake_row = {
            "id": "some-uuid",
            "chat_id": "-100123",
            "message_id": 42,
            "text": "Approve?",
            "state": "PENDING",
            "created_at": now,
            "expires_at": None,
            "answer": None,
        }
        with patch(
            "tg_tunnel.services.prompts.models.get_prompt",
            new=AsyncMock(return_value=fake_row),
        ):
            resp = await client.get("/v1/prompts/%231")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "some-uuid"
        assert data["text"] == "Approve?"
        assert data["state"] == "PENDING"
