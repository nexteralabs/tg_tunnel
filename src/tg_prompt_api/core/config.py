from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, SecretStr, field_validator, model_validator


_DEFAULT_SIGNING_SECRET = "super-secret"
_DEFAULT_WEBHOOK_SECRET = "change-me"


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: SecretStr
    TELEGRAM_TARGET_CHAT_ID: str
    TELEGRAM_MESSAGE_PARSE_MODE: str = "HTML"

    TELEGRAM_USE_WEBHOOK: bool = False
    PUBLIC_WEBHOOK_URL: str | None = None
    TELEGRAM_WEBHOOK_SECRET: SecretStr = SecretStr(_DEFAULT_WEBHOOK_SECRET)

    DATABASE_URL: AnyUrl

    CALLBACK_SIGNING_SECRET: SecretStr = SecretStr(_DEFAULT_SIGNING_SECRET)

    CLEAN_ON_BOOT: bool = True

    USE_AUTH: bool = False
    API_KEY: SecretStr | None = None

    MEDIA_ALLOWED_DIR: str | None = None
    MAX_MEDIA_SIZE_MB: int = 2  # Maximum file size for media_path uploads (Telegram photo limit)

    ENABLE_DOCS: bool = False  # Expose /docs, /redoc, /openapi.json (disable in prod)

    # Channel Gateway settings
    CHANNEL_CALLBACK_MAX_RETRIES: int = 3
    CHANNEL_CALLBACK_RETRY_DELAY: int = 5  # seconds
    CHANNEL_OFFLINE_NOTIFICATION: str = "Assistant offline, could not deliver message."

    @field_validator("TELEGRAM_BOT_TOKEN")
    @classmethod
    def validate_token_format(cls, v: SecretStr) -> SecretStr:
        token = v.get_secret_value()
        if ":" not in token or len(token.split(":")[0]) < 8:
            raise ValueError("Invalid Telegram bot token format")
        return v

    @model_validator(mode="after")
    def validate_secrets_and_auth(self) -> "Settings":
        if self.CALLBACK_SIGNING_SECRET.get_secret_value() == _DEFAULT_SIGNING_SECRET:
            raise ValueError(
                "CALLBACK_SIGNING_SECRET is still set to the default value. "
                "Set a strong unique secret in your .env file."
            )
        if self.TELEGRAM_WEBHOOK_SECRET.get_secret_value() == _DEFAULT_WEBHOOK_SECRET:
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET is still set to the default value. "
                "Set a strong unique secret in your .env file."
            )
        if self.USE_AUTH and self.API_KEY is None:
            raise ValueError("API_KEY must be set when USE_AUTH=true")
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
