"""
Unit tests for Settings validation — each test instantiates a fresh Settings
rather than mutating the singleton, so there are no ordering side-effects.
"""
import pytest
from pydantic import ValidationError

# Import the class, NOT the singleton
from tg_prompt_api.core.config import Settings


def _base_env(monkeypatch, **overrides):
    """Apply a complete minimal valid env-var set, then apply overrides."""
    base = {
        "TELEGRAM_BOT_TOKEN": "123456789:AABBCCDDEEFFaabbccddeeff-1234567890",
        "TELEGRAM_TARGET_CHAT_ID": "-1001234567890",
        "DATABASE_URL": "postgresql+psycopg://postgres:test@localhost:5432/test_db",
        "CALLBACK_SIGNING_SECRET": "test-signing-secret-32-chars-long!",
    }
    base.update(overrides)
    for key, value in base.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


class TestSettingsValidation:
    def test_use_auth_true_without_api_key_raises(self, monkeypatch):
        _base_env(monkeypatch, USE_AUTH="true", API_KEY=None)
        monkeypatch.delenv("API_KEY", raising=False)
        with pytest.raises(ValidationError, match="API_KEY"):
            Settings()

    def test_use_auth_true_with_api_key_succeeds(self, monkeypatch):
        _base_env(monkeypatch, USE_AUTH="true", API_KEY="my-secret-api-key")
        s = Settings()
        assert s.USE_AUTH is True
        assert s.API_KEY.get_secret_value() == "my-secret-api-key"

    def test_use_auth_false_without_api_key_succeeds(self, monkeypatch):
        _base_env(monkeypatch, USE_AUTH="false")
        monkeypatch.delenv("API_KEY", raising=False)
        s = Settings()
        assert s.USE_AUTH is False
        assert s.API_KEY is None

    def test_missing_database_url_raises(self, monkeypatch):
        _base_env(monkeypatch)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_invalid_bot_token_format_raises(self, monkeypatch):
        # Token must have ":" and the part before ":" must be at least 8 chars
        _base_env(monkeypatch, TELEGRAM_BOT_TOKEN="badtoken")
        with pytest.raises(ValidationError, match="bot token"):
            Settings()

    def test_bot_token_too_short_prefix_raises(self, monkeypatch):
        # "1234:token" — prefix is only 4 chars, needs at least 8
        _base_env(monkeypatch, TELEGRAM_BOT_TOKEN="1234:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef")
        with pytest.raises(ValidationError, match="bot token"):
            Settings()

    def test_valid_bot_token_accepted(self, monkeypatch):
        _base_env(monkeypatch)
        s = Settings()
        assert ":" in s.TELEGRAM_BOT_TOKEN.get_secret_value()

    def test_missing_telegram_target_chat_id_raises(self, monkeypatch):
        _base_env(monkeypatch)
        monkeypatch.delenv("TELEGRAM_TARGET_CHAT_ID", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_default_use_auth_is_false(self, monkeypatch):
        _base_env(monkeypatch)
        monkeypatch.delenv("USE_AUTH", raising=False)
        s = Settings()
        assert s.USE_AUTH is False

    def test_clean_on_boot_defaults_to_true(self, monkeypatch):
        _base_env(monkeypatch)
        monkeypatch.delenv("CLEAN_ON_BOOT", raising=False)
        s = Settings()
        assert s.CLEAN_ON_BOOT is True
