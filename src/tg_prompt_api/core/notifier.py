import json
import httpx
from .util import sign_body, retryable_http_post, resolve_callback_url


async def notify_callback(callback_url: str, payload: dict):
    callback_url = resolve_callback_url(callback_url)
    print(f"Sending callback to {callback_url} with payload: {json.dumps(payload, indent=2)}")
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "X-Signature": sign_body(body)}
    async with httpx.AsyncClient(timeout=10) as cx:
        await retryable_http_post(cx, callback_url, body, headers)
    print(f"Callback sent successfully to {callback_url}")
