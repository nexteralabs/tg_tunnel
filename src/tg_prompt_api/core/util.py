import hmac
import hashlib
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from tenacity import retry, wait_exponential_jitter, stop_after_attempt
from .config import settings

_IN_DOCKER = os.path.exists("/.dockerenv")


def resolve_callback_url(url: str) -> str:
    """Rewrite localhost URLs to host.docker.internal when running in Docker."""
    if not _IN_DOCKER:
        return url
    parsed = urlparse(url)
    if parsed.hostname in ("localhost", "127.0.0.1"):
        parsed = parsed._replace(
            netloc=parsed.netloc.replace(parsed.hostname, "host.docker.internal")
        )
        return urlunparse(parsed)
    return url


def validate_callback_url(url: str) -> None:
    """Raise ValueError if the URL scheme is not http/https or if the host is a
    private/reserved IP address.  Hostnames (non-IP strings) are allowed without
    DNS resolution."""
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Callback URL scheme must be http or https, got '{parsed.scheme}'")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Callback URL must have a non-empty hostname")

    # Only validate raw IP addresses — hostnames are passed through as-is.
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # Not a raw IP address — it's a hostname; allow it.
        return

    if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local:
        raise ValueError(
            f"Callback URL hostname '{hostname}' resolves to a private or reserved IP address"
        )


def validate_media_path(path: str) -> None:
    """Raise ValueError if the path escapes the configured MEDIA_ALLOWED_DIR."""
    if not settings.MEDIA_ALLOWED_DIR:
        raise ValueError("media_path requires MEDIA_ALLOWED_DIR to be configured")

    allowed = Path(settings.MEDIA_ALLOWED_DIR).resolve()
    target = Path(path).resolve()

    if not str(target).startswith(str(allowed)):
        raise ValueError(
            f"Path '{path}' is outside the allowed media directory '{settings.MEDIA_ALLOWED_DIR}'"
        )


def sign_body(body: bytes) -> str:
    sig = hmac.new(
        settings.CALLBACK_SIGNING_SECRET.get_secret_value().encode(), body, hashlib.sha256
    ).hexdigest()
    return f"sha256={sig}"


@retry(wait=wait_exponential_jitter(initial=0.5, max=8), stop=stop_after_attempt(5))
async def retryable_http_post(client, url: str, body: bytes, headers: dict):
    resp = await client.post(url, content=body, headers=headers)
    resp.raise_for_status()
    return resp
