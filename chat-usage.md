# Telegram Channel Gateway - Usage Guide

## Overview

The Channel Gateway enables bidirectional communication between your application and Telegram channels using dedicated bot tokens.

**Two channel types:**
- **MESSAGE channels**: Bidirectional - forward incoming messages to your app, send outgoing messages
- **PROMPT channels**: System-managed - used internally for prompt lifecycle (auto-created at startup)

## Quick Start

### 1. Register a Channel

```bash
POST /register-channel
{
  "channel_id": "my-assistant",
  "telegram_chat_id": "-1001234567890",
  "bot_token": "7123456789:AAE...",
  "callback_url": "https://your-app.com/webhook/messages",
  "channel_type": "MESSAGE"
}
```

**Parameters:**
- `channel_id`: Your identifier (used in API calls)
- `telegram_chat_id`: Telegram chat/channel ID (get via @userinfobot)
- `bot_token`: Bot token from @BotFather
- `callback_url`: Your endpoint for incoming messages
- `channel_type`: `MESSAGE` (default) or `PROMPT`

**Note:** Re-registering updates configuration (idempotent)

### 2. Receive Messages (Implement Callback)

Your `callback_url` receives:
```json
{
  "type": "telegram.message.created",
  "channel_id": "my-assistant",
  "telegram_chat_id": "-1001234567890",
  "from": "username",
  "text": "Hello from Telegram!"
}
```

Return `200 OK` to acknowledge. Non-200 triggers 3 retries (5s delay).

**`from` field priority:**
1. Telegram username (e.g., `"john_doe"`)
2. First name (e.g., `"Georges"`)
3. User ID (e.g., `"user_8371985836"`)
4. `"unknown"`

### 3. Send Simple Messages

```bash
POST /send
{
  "channel_id": "my-assistant",
  "text": "Hello from my app!"
}
```

Use for notifications without needing user response.

### 4. Send Interactive Prompts with Buttons

```bash
POST /v1/prompts
{
  "channel_id": "my-assistant",
  "text": "Approve deployment?",
  "options": ["Approve", "Reject"],
  "callback_url": "https://your-app.com/webhook/prompts"
}
```

**Key difference from `/send`:**
- Buttons appear in Telegram
- User response tracked (PENDING → ANSWERED)
- Callback sent when button clicked
- HMAC-signed callback for security
- TTL/expiration support

**Callback behavior:**
- Prompt's `callback_url` → receives button responses
- Channel's `callback_url` → receives incoming messages

This allows routing to different endpoints.

## Channel Management

### List Channels
```bash
GET /channels
```

Returns all active channels (excluding bot tokens for security).

### Unregister Channel
```bash
DELETE /channels/{channel_id}
```

Stops polling and marks inactive (keeps database record).

## Comparison: /send vs /v1/prompts

| Feature | `/send` | `/v1/prompts` |
|---------|---------|---------------|
| Use case | Notifications | Approvals/decisions |
| Buttons | ❌ | ✅ |
| Response tracking | ❌ | ✅ |
| Callback | ❌ | ✅ (HMAC signed) |
| Expiration | ❌ | ✅ |

## Configuration

Environment variables:
```bash
CHANNEL_CALLBACK_MAX_RETRIES=3
CHANNEL_CALLBACK_RETRY_DELAY=5
CHANNEL_OFFLINE_NOTIFICATION="Assistant offline, could not deliver message."
```

## Getting Telegram Chat ID

**Method 1:** Add @userinfobot to your channel → send message → get ID

**Method 2:** `curl "https://api.telegram.org/bot<TOKEN>/getUpdates"` → look for `"chat":{"id":-100...}`

**Method 3:** Register channel → send test message → check Gateway logs

## Common Issues

**Conflict error (duplicate polling):**
- Each bot token can only have ONE polling instance
- Don't run multiple Gateway instances with same bot

**Callback not called:**
- Verify callback URL is publicly accessible (use ngrok for local dev)
- Check endpoint returns 200 OK
- Test: `curl -X POST <callback_url> -d '{"test":"ok"}'`

**Messages not sending:**
- Verify bot is admin in channel
- Check `telegram_chat_id` is correct (negative for channels)
- Verify `is_active=true`: `GET /channels`

## Complete Example

```python
import httpx

GATEWAY = "http://localhost:8100"

# 1. Register channel (once at startup)
async def setup():
    async with httpx.AsyncClient() as client:
        await client.post(f"{GATEWAY}/register-channel", json={
            "channel_id": "my-bot",
            "telegram_chat_id": "-1001234567890",
            "bot_token": "YOUR_TOKEN",
            "callback_url": "https://your-app.com/telegram"
        })

# 2. Handle incoming messages
@app.post("/telegram")
async def handle_telegram(request: Request):
    data = await request.json()
    message = data["text"]

    # Process and respond
    response = await process_message(message)
    await send_to_telegram("my-bot", response)

    return {"status": "ok"}

# 3. Send simple message
async def send_to_telegram(channel_id: str, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{GATEWAY}/send", json={
            "channel_id": channel_id,
            "text": text
        })

# 4. Send prompt with buttons
async def request_approval(channel_id: str, question: str):
    async with httpx.AsyncClient() as client:
        result = await client.post(f"{GATEWAY}/v1/prompts", json={
            "channel_id": channel_id,
            "text": question,
            "options": ["Approve", "Reject"],
            "callback_url": "https://your-app.com/approvals"
        })
        return result.json()["prompt_id"]
```

## Production Checklist

- ✅ Use HTTPS for callback URLs
- ✅ Ensure callback endpoint is publicly accessible
- ✅ Return 200 OK from callbacks within 5 seconds
- ✅ Store bot tokens securely (environment variables)
- ✅ Monitor Gateway logs for errors
- ✅ Use different bots for dev/staging/production
- ✅ Set appropriate `CHANNEL_CALLBACK_MAX_RETRIES`

## Testing

Use [webhook.site](https://webhook.site) to inspect callbacks without writing code:

1. Register channel with webhook.site URL
2. Send message in Telegram
3. View payload at webhook.site
4. Verify format matches documentation

For local development, use ngrok:
```bash
ngrok http 3000
# Use the HTTPS URL as callback_url
```
