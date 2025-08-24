from pydantic_settings import BaseSettings
from pydantic import AnyUrl, SecretStr, field_validator


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: SecretStr
    TELEGRAM_TARGET_CHAT_ID: str
    TELEGRAM_MESSAGE_PARSE_MODE: str = "HTML"

    TELEGRAM_USE_WEBHOOK: bool = False
    PUBLIC_WEBHOOK_URL: str | None = None
    TELEGRAM_WEBHOOK_SECRET: SecretStr = SecretStr("change-me")

    DATABASE_URL: AnyUrl = "postgresql+psycopg://postgres:postgres@localhost:5432/tg_prompt_api"

    CALLBACK_SIGNING_SECRET: SecretStr = SecretStr("super-secret")

    CLEAN_ON_BOOT: bool = True

    @field_validator("TELEGRAM_BOT_TOKEN")
    @classmethod
    def validate_token_format(cls, v: SecretStr) -> SecretStr:
        """Validate Telegram bot token format"""
        token = v.get_secret_value()
        if ":" not in token or len(token.split(":")[0]) < 8:
            raise ValueError("Invalid Telegram bot token format")
        return v

    class Config:
        env_file = ".env"


settings = Settings()
