"""
Unit tests for tg_gateway.services.channels.models.

Verifies SQL-level correctness (COALESCE preservation, SELECT *, WHERE is_active, etc.)
by capturing the SQL string passed to the patched core.db module-level functions.
"""
from unittest.mock import AsyncMock, MagicMock, patch


def _make_conn():
    """Return a throwaway MagicMock representing a psycopg connection."""
    return MagicMock()


# ---------------------------------------------------------------------------
# register_channel
# ---------------------------------------------------------------------------


class TestRegisterChannel:
    async def test_preserves_last_update_id_on_re_register(self):
        """Regression: re-registering a channel must NOT reset last_update_id.

        The SQL uses COALESCE(channels.last_update_id, 0) so that the existing
        polling offset is preserved on idempotent re-registration.
        """
        from tg_gateway.services.channels.models import register_channel

        conn = _make_conn()
        captured_sql = []

        async def _capture_execute(aconn, sql, *params):
            captured_sql.append(sql)

        # Patch at the models' import location, not at core.db, because the
        # module already imported `execute` by name at load time.
        with patch("tg_gateway.services.channels.models.execute", new=_capture_execute):
            await register_channel(
                conn,
                "my-channel",
                "-100111",
                "fake-bot-token",
                "http://cb.example.com/callback",
                "MESSAGE",
            )

        assert len(captured_sql) == 1
        sql = captured_sql[0]
        assert "COALESCE" in sql, "SQL must use COALESCE to preserve last_update_id"
        assert "last_update_id" in sql

    async def test_new_channel_sets_is_active_true(self):
        """New channel registration must include is_active = true in the upsert."""
        from tg_gateway.services.channels.models import register_channel

        conn = _make_conn()
        captured_sql = []

        async def _capture_execute(aconn, sql, *params):
            captured_sql.append(sql)

        with patch("tg_gateway.services.channels.models.execute", new=_capture_execute):
            await register_channel(
                conn,
                "new-ch",
                "-100222",
                "token",
                None,
                "PROMPT",
            )

        assert len(captured_sql) == 1
        sql = captured_sql[0]
        assert "is_active" in sql
        assert "true" in sql.lower()


# ---------------------------------------------------------------------------
# list_active_channels
# ---------------------------------------------------------------------------


class TestListActiveChannels:
    async def test_returns_all_columns_including_bot_token(self):
        """Regression: list_active_channels must use SELECT * so bot_token is available
        to the poller (which needs it to create the bot instance).
        """
        from tg_gateway.services.channels.models import list_active_channels

        conn = _make_conn()
        captured_sql = []

        async def _capture_fetchall(aconn, sql, *params):
            captured_sql.append(sql)
            return []

        with patch("tg_gateway.services.channels.models.fetchall", new=_capture_fetchall):
            await list_active_channels(conn)

        assert len(captured_sql) == 1
        sql = captured_sql[0]
        # Must use SELECT * (not a hand-picked column list that might omit bot_token)
        assert "SELECT *" in sql or "select *" in sql.lower()

    async def test_only_returns_active_channels(self):
        """SQL must filter WHERE is_active = true so inactive channels are excluded."""
        from tg_gateway.services.channels.models import list_active_channels

        conn = _make_conn()
        captured_sql = []

        async def _capture_fetchall(aconn, sql, *params):
            captured_sql.append(sql)
            return []

        with patch("tg_gateway.services.channels.models.fetchall", new=_capture_fetchall):
            await list_active_channels(conn)

        sql = captured_sql[0]
        assert "is_active" in sql
        assert "true" in sql.lower()


# ---------------------------------------------------------------------------
# deactivate_channel
# ---------------------------------------------------------------------------


class TestDeactivateChannel:
    async def test_sets_is_active_false(self):
        """deactivate_channel issues UPDATE SET is_active = false for the given channel_id."""
        from tg_gateway.services.channels.models import deactivate_channel

        conn = _make_conn()
        captured: list[tuple] = []

        async def _capture_execute(aconn, sql, *params):
            captured.append((sql, params))

        with patch("tg_gateway.services.channels.models.execute", new=_capture_execute):
            await deactivate_channel(conn, "my-channel")

        assert len(captured) == 1
        sql, params = captured[0]
        assert "is_active" in sql
        assert "false" in sql.lower()
        # The channel_id is passed as a parameter, not interpolated into SQL
        assert "my-channel" in params
