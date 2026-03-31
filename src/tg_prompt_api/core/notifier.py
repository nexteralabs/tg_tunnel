import asyncio
import json
import logging
import httpx
from .util import sign_body, retryable_http_post, resolve_callback_url

logger = logging.getLogger(__name__)

_bg_tasks: set[asyncio.Task] = set()
_MAX_PENDING_CALLBACKS = 200


async def notify_callback(callback_url: str, payload: dict):
    prompt_id = payload.get("prompt_id", payload.get("id", "unknown"))
    callback_url = resolve_callback_url(callback_url)
    logger.info("Sending callback prompt_id=%s to %s", prompt_id, callback_url)
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "X-Signature": sign_body(body)}
    async with httpx.AsyncClient(timeout=10) as cx:
        await retryable_http_post(cx, callback_url, body, headers)
    logger.debug("Callback sent successfully to %s", callback_url)


def schedule_callback(callback_url: str, payload: dict) -> None:
    """Fire-and-forget: schedule notify_callback as a background asyncio Task."""

    if len(_bg_tasks) >= _MAX_PENDING_CALLBACKS:
        prompt_id = payload.get("prompt_id", payload.get("id", "unknown"))
        logger.error(
            "Callback queue full (%d pending), dropping callback for prompt_id=%s",
            len(_bg_tasks),
            prompt_id,
        )
        return

    async def _run():
        try:
            await notify_callback(callback_url, payload)
        except Exception:
            prompt_id = payload.get("prompt_id", payload.get("id", "unknown"))
            logger.exception("Failed to send callback prompt_id=%s to %s", prompt_id, callback_url)

    task = asyncio.create_task(_run())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
