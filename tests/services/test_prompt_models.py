"""
Unit tests for tg_gateway.services.prompts.models.

All database I/O (fetchone, fetchall, execute) is patched at the module level in
tg_gateway.core.db so no real PostgreSQL connection is needed.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn():
    """Return a throwaway MagicMock representing a psycopg connection."""
    return MagicMock()


# ---------------------------------------------------------------------------
# mark_answered
# ---------------------------------------------------------------------------


class TestMarkAnswered:
    async def test_returns_callback_info_when_callback_url_set(self):
        """mark_answered returns {"callback_url": ..., "payload": ...} when callback_url is set."""
        from tg_gateway.services.prompts.models import mark_answered

        answered_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        fake_prompt = {
            "prompt_num": 1,
            "callback_url": "http://myapp.example.com/webhook",
            "correlation_id": "corr-abc",
            "text": "Approve deployment?",
            "answered_at": answered_at,
            "state": "ANSWERED",
        }

        conn = _make_conn()

        with (
            patch("tg_gateway.services.prompts.models.execute", new=AsyncMock()),
            patch("tg_gateway.services.prompts.models.fetchone", new=AsyncMock(return_value=fake_prompt)),
        ):
            result = await mark_answered(
                conn,
                "#1",
                answer_type="option",
                value="Approve",
                user_id=999,
                username="alice",
            )

        assert result is not None
        assert result["callback_url"] == "http://myapp.example.com/webhook"
        payload = result["payload"]
        assert payload["prompt_id"] == "#1"
        assert payload["correlation_id"] == "corr-abc"
        assert payload["text"] == "Approve deployment?"
        assert payload["answer"]["type"] == "option"
        assert payload["answer"]["value"] == "Approve"
        assert payload["answer"]["user_id"] == 999
        assert payload["answer"]["username"] == "alice"

    async def test_returns_none_when_no_callback_url(self):
        """mark_answered returns None when the prompt has no callback_url."""
        from tg_gateway.services.prompts.models import mark_answered

        fake_prompt = {
            "prompt_num": 2,
            "callback_url": None,
            "correlation_id": None,
            "text": "Scale down?",
            "answered_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
            "state": "ANSWERED",
        }

        conn = _make_conn()

        with (
            patch("tg_gateway.services.prompts.models.execute", new=AsyncMock()),
            patch("tg_gateway.services.prompts.models.fetchone", new=AsyncMock(return_value=fake_prompt)),
        ):
            result = await mark_answered(
                conn,
                "#2",
                answer_type="text",
                value="yes please",
                user_id=None,
                username=None,
            )

        assert result is None

    async def test_documents_non_idempotent_behaviour(self):
        """Behaviour documentation: mark_answered always returns callback info if callback_url is
        set, regardless of whether the UPDATE WHERE state=PENDING actually matched any row.

        This means calling mark_answered a second time (after the prompt is already ANSWERED)
        will still return callback info — callers must deduplicate if needed.
        """
        from tg_gateway.services.prompts.models import mark_answered

        answered_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        already_answered_prompt = {
            "prompt_num": 3,
            "callback_url": "http://myapp.example.com/webhook",
            "correlation_id": None,
            "text": "Question?",
            "answered_at": answered_at,
            "state": "ANSWERED",  # already answered — UPDATE matched 0 rows
        }

        conn = _make_conn()

        with (
            patch("tg_gateway.services.prompts.models.execute", new=AsyncMock()),
            # get_prompt still returns the row even on second call
            patch("tg_gateway.services.prompts.models.fetchone", new=AsyncMock(return_value=already_answered_prompt)),
        ):
            result = await mark_answered(
                conn,
                "#3",
                answer_type="option",
                value="Yes",
                user_id=1,
                username="bob",
            )

        # Current behaviour: returns callback info even on a redundant call.
        # This test documents it so future devs know to add idempotency if needed.
        assert result is not None
        assert result["callback_url"] == "http://myapp.example.com/webhook"

    async def test_answered_at_is_isoformat_string(self):
        """The answered_at in the callback payload is an ISO 8601 formatted string."""
        from tg_gateway.services.prompts.models import mark_answered

        answered_at = datetime(2024, 6, 15, 9, 30, 0, tzinfo=timezone.utc)
        fake_prompt = {
            "prompt_num": 4,
            "callback_url": "http://example.com/cb",
            "correlation_id": None,
            "text": "Test?",
            "answered_at": answered_at,
            "state": "ANSWERED",
        }

        conn = _make_conn()

        with (
            patch("tg_gateway.services.prompts.models.execute", new=AsyncMock()),
            patch("tg_gateway.services.prompts.models.fetchone", new=AsyncMock(return_value=fake_prompt)),
        ):
            result = await mark_answered(
                conn,
                "#4",
                answer_type="option",
                value="OK",
                user_id=None,
                username=None,
            )

        assert result is not None
        answered_at_str = result["payload"]["answered_at"]
        assert isinstance(answered_at_str, str)
        # Must be parseable as ISO 8601
        parsed = datetime.fromisoformat(answered_at_str)
        assert parsed == answered_at


# ---------------------------------------------------------------------------
# create_prompt
# ---------------------------------------------------------------------------


class TestCreatePrompt:
    async def test_returns_hash_prefixed_id(self):
        """create_prompt returns a '#<n>' string where n is prompt_num from the RETURNING row."""
        from tg_gateway.services.prompts.models import create_prompt

        fake_row = {
            "prompt_num": 42,
            "id": "some-uuid",
            "chat_id": "-100123",
            "text": "Deploy?",
            "state": "PENDING",
            "message_id": None,
            "created_at": datetime.now(timezone.utc),
            "expires_at": None,
            "answer": None,
            "callback_url": None,
            "correlation_id": None,
            "media_url": None,
            "options": [],
            "allow_text": False,
        }

        conn = _make_conn()

        with patch("tg_gateway.services.prompts.models.fetchone", new=AsyncMock(return_value=fake_row)):
            prompt_id, row = await create_prompt(
                conn,
                chat_id="-100123",
                text="Deploy?",
                media_url=None,
                options=[],
                allow_text=False,
                callback_url=None,
                correlation_id=None,
                ttl_sec=3600,
            )

        assert prompt_id == "#42"

    async def test_returns_full_row(self):
        """create_prompt also returns the complete row dict alongside the formatted ID."""
        from tg_gateway.services.prompts.models import create_prompt

        now = datetime.now(timezone.utc)
        fake_row = {
            "prompt_num": 7,
            "id": "row-uuid",
            "chat_id": "-100999",
            "text": "Are you sure?",
            "state": "PENDING",
            "message_id": None,
            "created_at": now,
            "expires_at": None,
            "answer": None,
            "callback_url": "http://example.com/cb",
            "correlation_id": "corr-007",
            "media_url": None,
            "options": ["Yes", "No"],
            "allow_text": False,
        }

        conn = _make_conn()

        with patch("tg_gateway.services.prompts.models.fetchone", new=AsyncMock(return_value=fake_row)):
            prompt_id, row = await create_prompt(
                conn,
                chat_id="-100999",
                text="Are you sure?",
                media_url=None,
                options=["Yes", "No"],
                allow_text=False,
                callback_url="http://example.com/cb",
                correlation_id="corr-007",
                ttl_sec=3600,
            )

        assert prompt_id == "#7"
        assert row is fake_row
        assert row["chat_id"] == "-100999"
        assert row["callback_url"] == "http://example.com/cb"
