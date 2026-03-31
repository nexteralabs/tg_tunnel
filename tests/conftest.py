"""
Root conftest: set env vars BEFORE any project imports so Settings loads cleanly.
These module-level assignments run before pytest collects any test modules.
"""
import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456789:AABBCCDDEEFFaabbccddeeff-1234567890")
os.environ.setdefault("TELEGRAM_TARGET_CHAT_ID", "-1001234567890")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:test@localhost:5432/test_db")
os.environ.setdefault("CALLBACK_SIGNING_SECRET", "test-signing-secret-32-chars-long!")
