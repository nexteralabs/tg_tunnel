import json
import httpx
from .util import sign_body, retryable_http_post


async def notify_callback(callback_url: str, payload: dict):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "X-Signature": sign_body(body)}
    async with httpx.AsyncClient(timeout=10) as cx:
        await retryable_http_post(cx, callback_url, body, headers)
