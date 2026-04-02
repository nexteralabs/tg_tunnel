import logging
import re


class TokenRedactingFilter(logging.Filter):
    """Filter to redact sensitive tokens and secrets from logs"""

    def __init__(self):
        super().__init__()
        # Pattern to match Telegram bot tokens (flexible length after colon)
        self.token_pattern = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,}")
        # Pattern to match HMAC signatures
        self.signature_pattern = re.compile(r"sha256=[a-fA-F0-9]{64}")
        # Pattern to match generic secrets (long strings of alphanumeric characters)
        self.secret_pattern = re.compile(r"[A-Za-z0-9_-]{32,}")

    def filter(self, record):
        """Redact sensitive information from log records"""
        if hasattr(record, "msg") and record.msg:
            record.msg = self._redact_sensitive_data(str(record.msg))

        if hasattr(record, "args") and record.args:
            record.args = tuple(
                self._redact_sensitive_data(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )

        # Redact exception tracebacks before the logging Formatter renders them
        if record.exc_info:
            import traceback as _tb

            record.exc_text = self._redact_sensitive_data(
                "".join(_tb.format_exception(*record.exc_info))
            )
            record.exc_info = None  # Prevent the Formatter from re-rendering

        return True

    def _redact_sensitive_data(self, text: str) -> str:
        """Redact sensitive patterns from text"""
        # Redact Telegram bot tokens
        text = self.token_pattern.sub("[REDACTED_TOKEN]", text)
        # Redact HMAC signatures
        text = self.signature_pattern.sub("[REDACTED_SIGNATURE]", text)
        # Don't redact generic secrets as they're too broad and may catch legitimate data
        return text


def setup_secure_logging():
    """Setup logging with token redaction for all loggers"""
    token_filter = TokenRedactingFilter()

    # Apply to root logger to catch all logging
    root_logger = logging.getLogger()
    root_logger.addFilter(token_filter)

    # Also apply to specific loggers that might log sensitive data
    sensitive_loggers = ["tg_gateway", "aiogram", "httpx", "uvicorn"]

    for logger_name in sensitive_loggers:
        logger = logging.getLogger(logger_name)
        logger.addFilter(token_filter)
