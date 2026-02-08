# Telegram Prompt API - Integration Guide

This guide provides everything needed to integrate the Telegram Prompt API into your application for human-in-the-loop validations and approvals.

## Overview

The Prompt API allows your application to:
- Post approval prompts to Telegram with inline buttons
- Collect responses via button clicks or text patterns
- Receive webhook callbacks when prompts are answered
- Track prompt lifecycle and expiration
- Include media (images) with prompts

## Use Cases

- **Deployment Approvals**: "Deploy to production?" → [Approve] [Reject]
- **AI Action Validation**: "Execute this command?" → [Yes] [No]
- **Human-in-the-Loop Decisions**: Any scenario requiring human confirmation
- **Notification + Response**: Send alerts that require acknowledgment

## Quick Start

### 1. Create a Simple Prompt

**Endpoint:** `POST /v1/prompts`

**Request:**
```json
{
  "text": "Deploy to production?",
  "options": ["Approve", "Reject"],
  "callback_url": "https://your-app.com/webhook/prompts"
}
```

**Response:**
```json
{
  "prompt_id": "#123",
  "chat_id": "-1001234567890",
  "message_id": 456789
}
```

**What Happens:**
1. Message posted to configured Telegram chat with inline buttons
2. User clicks a button (or replies with text if enabled)
3. Your callback URL receives the response with HMAC signature
4. Prompt state changes from `PENDING` to `ANSWERED`

**cURL Example:**
```bash
curl -X POST http://localhost:8100/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Deploy to production?",
    "options": ["Approve", "Reject"],
    "callback_url": "https://your-app.com/webhook/prompts"
  }'
```

### 2. Implement Callback Endpoint

Your application must implement a webhook endpoint to receive prompt responses.

**Callback Payload:**
```json
{
  "prompt_id": "#123",
  "answer": {
    "selected_option": "Approve",
    "answered_at": "2025-01-15T10:30:45.123Z",
    "from_user": "john_doe"
  },
  "correlation_id": "deploy-2024-001",
  "state": "ANSWERED"
}
```

**HMAC Signature Verification:**

The callback includes an `X-Signature` header for verification:

```
X-Signature: sha256=abc123def456...
```

**Python Example:**
```python
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib

app = FastAPI()

SIGNING_SECRET = "your-secret-from-env"  # Must match gateway's CALLBACK_SIGNING_SECRET

def verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        SIGNING_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

@app.post("/webhook/prompts")
async def prompt_callback(request: Request):
    # Get raw body and signature
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    # Verify signature
    if not verify_signature(body, signature):
        raise HTTPException(401, "Invalid signature")

    # Parse payload
    import json
    payload = json.loads(body)

    prompt_id = payload["prompt_id"]
    answer = payload["answer"]["selected_option"]
    correlation_id = payload.get("correlation_id")

    print(f"Prompt {prompt_id} answered: {answer}")

    # Process the response
    if answer == "Approve":
        await execute_deployment(correlation_id)
    else:
        await cancel_deployment(correlation_id)

    return {"status": "ok"}
```

**Node.js Example:**
```javascript
const express = require('express');
const crypto = require('crypto');

const app = express();
app.use(express.raw({ type: 'application/json' }));

const SIGNING_SECRET = process.env.CALLBACK_SIGNING_SECRET;

function verifySignature(body, signature) {
  const expected = crypto
    .createHmac('sha256', SIGNING_SECRET)
    .update(body)
    .digest('hex');

  return crypto.timingSafeEqual(
    Buffer.from(`sha256=${expected}`),
    Buffer.from(signature)
  );
}

app.post('/webhook/prompts', (req, res) => {
  const signature = req.headers['x-signature'];

  if (!verifySignature(req.body, signature)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  const payload = JSON.parse(req.body.toString());
  const { prompt_id, answer, correlation_id } = payload;

  console.log(`Prompt ${prompt_id} answered: ${answer.selected_option}`);

  // Process response
  if (answer.selected_option === 'Approve') {
    executeDeployment(correlation_id);
  } else {
    cancelDeployment(correlation_id);
  }

  res.json({ status: 'ok' });
});

app.listen(3000);
```

## Using Prompts with Custom Channels

By default, prompts use the system prompt channel (`__system_prompt__`), which is automatically configured at startup. You can also send prompts through registered MESSAGE channels, allowing different applications to have their own dedicated bot tokens.

### When to Use Custom Channels

- **Dedicated bot per application**: Each app uses its own bot token
- **Separate chat isolation**: Different apps post to different Telegram chats
- **Independent callback URLs**: Each channel has its own default callback

### Example: Sending Prompt via Custom Channel

**Step 1: Register a MESSAGE channel**
```bash
curl -X POST http://localhost:8100/register-channel \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "my-ai-assistant",
    "telegram_chat_id": "-1001234567890",
    "bot_token": "YOUR_BOT_TOKEN",
    "callback_url": "https://my-app.com/webhook/messages",
    "channel_type": "MESSAGE"
  }'
```

**Step 2: Send prompt via that channel**
```bash
curl -X POST http://localhost:8100/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "my-ai-assistant",
    "text": "Execute this command?",
    "options": ["Yes", "No"],
    "callback_url": "https://my-app.com/webhook/prompts"
  }'
```

**Key Points:**
- The prompt uses the channel's bot token and chat ID
- The `callback_url` in the prompt request **overrides** the channel's registered callback URL
- Button responses are sent to the prompt's `callback_url`, not the channel's
- This allows MESSAGE channels to both receive messages and send prompts

## API Reference

### Create Prompt (JSON)

**Endpoint:** `POST /v1/prompts`

**Request Body:**
```json
{
  "channel_id": "my-assistant",       // Optional: Channel to use (defaults to __system_prompt__)
  "chat_id": "-1001234567890",        // DEPRECATED: Use channel_id instead
  "text": "Your prompt message",      // Required
  "media_url": "https://...",         // Optional: Image URL
  "media_path": "C:\\images\\...",    // Optional: Server-side file path
  "options": ["Yes", "No"],           // Optional: Button labels
  "allow_text": false,                // Optional: Allow text responses
  "callback_url": "https://...",      // Optional: Webhook URL
  "correlation_id": "deploy-001",     // Optional: Your reference ID
  "ttl_sec": 3600                     // Optional: Expiration (default: 1 hour)
}
```

**Field Details:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | - | The prompt message to display |
| `channel_id` | string | No | `__system_prompt__` | Channel to use for this prompt |
| `chat_id` | string/int | No | From channel | DEPRECATED: Use channel_id instead |
| `media_url` | string | No | null | URL to image (publicly accessible) |
| `media_path` | string | No | null | Server-side file path (for local files) |
| `options` | string[] | No | [] | Button labels (max 8 recommended) |
| `allow_text` | boolean | No | false | Allow `ID:#123 response` text pattern |
| `callback_url` | string | No | null | Your webhook endpoint |
| `correlation_id` | string | No | null | Your tracking ID (returned in callback) |
| `ttl_sec` | integer | No | 3600 | Time-to-live (0-604800, max 7 days) |

**Response:**
```json
{
  "prompt_id": "#123",
  "chat_id": "-1001234567890",
  "message_id": 456789
}
```

**Error Responses:**

| Status | Error | Description |
|--------|-------|-------------|
| 400 | `ValueError` | Invalid parameters (e.g., both media_url and media_path) |
| 400 | `file_not_found` | media_path file doesn't exist |
| 500 | `RuntimeError` | Failed to post to Telegram |

### Create Prompt with File Upload

**Endpoint:** `POST /v1/prompts/upload`

Use this endpoint when you want to upload an image file directly (not via URL or server path).

**Content-Type:** `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | - | The prompt message |
| `file` | file | No | null | Image file to upload |
| `chat_id` | string | No | From config | Telegram chat ID |
| `media_url` | string | No | null | Alternative to file upload |
| `options` | string | No | "[]" | JSON array: `["Yes", "No"]` |
| `allow_text` | boolean | No | false | Allow text responses |
| `callback_url` | string | No | null | Webhook URL |
| `correlation_id` | string | No | null | Your reference ID |
| `ttl_sec` | integer | No | 3600 | Time-to-live in seconds |

**cURL Example:**
```bash
curl -X POST http://localhost:8100/v1/prompts/upload \
  -F "text=Review this screenshot" \
  -F "file=@/path/to/image.png" \
  -F "options=[\"Approve\", \"Reject\"]" \
  -F "callback_url=https://your-app.com/webhook/prompts"
```

**Python Example:**
```python
import httpx

async def create_prompt_with_image(text: str, image_path: str):
    async with httpx.AsyncClient() as client:
        with open(image_path, 'rb') as f:
            response = await client.post(
                "http://localhost:8100/v1/prompts/upload",
                data={
                    "text": text,
                    "options": '["Approve", "Reject"]',
                    "callback_url": "https://your-app.com/webhook/prompts"
                },
                files={"file": ("screenshot.png", f, "image/png")}
            )
    return response.json()
```

### Get Prompt Status

**Endpoint:** `GET /v1/prompts/{prompt_id}`

**Response:**
```json
{
  "id": "#123",
  "chat_id": "-1001234567890",
  "message_id": 456789,
  "text": "Deploy to production?",
  "state": "ANSWERED",
  "created_at": "2025-01-15T10:30:00Z",
  "expires_at": "2025-01-15T11:30:00Z",
  "answer": {
    "selected_option": "Approve",
    "answered_at": "2025-01-15T10:30:45.123Z",
    "from_user": "john_doe"
  }
}
```

**States:**
- `PENDING` - Waiting for response
- `ANSWERED` - Response received
- `EXPIRED` - TTL reached without answer

**cURL Example:**
```bash
curl http://localhost:8100/v1/prompts/%23123
```

**Note:** URL-encode the `#` character as `%23`

### List Pending Prompts

**Endpoint:** `GET /v1/prompts/pending`

**Response:**
```json
[
  {
    "id": "#123",
    "chat_id": "-1001234567890",
    "message_id": 456789,
    "text": "Deploy to production?",
    "state": "PENDING",
    "created_at": "2025-01-15T10:30:00Z",
    "expires_at": "2025-01-15T11:30:00Z",
    "answer": null
  },
  {
    "id": "#124",
    "chat_id": "-1001234567890",
    "message_id": 456790,
    "text": "Approve this change?",
    "state": "PENDING",
    "created_at": "2025-01-15T10:31:00Z",
    "expires_at": "2025-01-15T11:31:00Z",
    "answer": null
  }
]
```

**cURL Example:**
```bash
curl http://localhost:8100/v1/prompts/pending
```

## Response Methods

### Method 1: Inline Buttons (Recommended)

Users click buttons directly in the Telegram message.

**Setup:**
```json
{
  "text": "Approve deployment?",
  "options": ["Approve", "Reject"]
}
```

**User Experience:**
1. Message appears with buttons
2. User clicks a button
3. Buttons disappear, confirmation message appears
4. Your callback receives the response

**Best For:**
- Simple yes/no decisions
- Multiple choice (up to 8 options recommended)
- Quick responses

### Method 2: Text Pattern

Users reply with `ID:#123 their response` format.

**Setup:**
```json
{
  "text": "What's your feedback?",
  "allow_text": true
}
```

**User Experience:**
1. Message appears (no buttons)
2. User replies: `ID:#123 Looks good to me!`
3. Your callback receives: `"selected_option": "Looks good to me!"`

**Best For:**
- Free-form responses
- When buttons are too limiting
- Collecting detailed feedback

### Method 3: Combined

Both buttons and text responses allowed.

**Setup:**
```json
{
  "text": "Review this code",
  "options": ["LGTM", "Needs Changes"],
  "allow_text": true
}
```

**Best For:**
- Quick options + custom response option
- Flexibility for power users

## Media Support

### Option 1: Public URL

**Usage:**
```json
{
  "text": "Approve this design?",
  "media_url": "https://i.imgur.com/abc123.jpg"
}
```

**Requirements:**
- URL must be publicly accessible
- Telegram must be able to fetch it
- Supported formats: JPG, PNG, GIF

### Option 2: Server-Side File Path

**Usage:**
```json
{
  "text": "Review this screenshot",
  "media_path": "C:\\screenshots\\latest.png"
}
```

**Requirements:**
- File must exist on the server running the API
- Absolute or relative path from server's working directory
- Useful for locally generated images

**Note:** Cannot use both `media_url` and `media_path` - choose one.

### Option 3: File Upload

**Usage:**
```bash
curl -X POST http://localhost:8100/v1/prompts/upload \
  -F "text=Review this" \
  -F "file=@./image.png"
```

**Requirements:**
- Use `multipart/form-data` content type
- Use the `/v1/prompts/upload` endpoint
- Cannot combine with `media_url`

## Configuration

### Required Environment Variables

```bash
# Telegram bot credentials
TELEGRAM_BOT_TOKEN=7123456789:AAEabcdefghijklmnopqrstuvwxyz123456
TELEGRAM_TARGET_CHAT_ID=-1001234567890  # Default chat for prompts

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/telegram_prompts

# Callback security
CALLBACK_SIGNING_SECRET=your-random-secret-key-here

# Optional: Auto-cleanup on boot
CLEAN_ON_BOOT=true
```

### Getting Your Chat ID

**Method 1: Using @userinfobot**
1. Add @userinfobot to your chat/group/channel
2. Send any message
3. Bot replies with chat ID

**Method 2: Using bot.getUpdates**
```bash
# Send a message to your bot first, then:
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"

# Look for "chat":{"id":-1001234567890}
```

**Method 3: Using the API logs**
```bash
# Start the API with logging
poetry run prompt-cli run_api

# Send /ping to your bot
# Check logs for chat_id
```

### Creating a Bot Token

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow prompts to choose name and username
4. Receive bot token: `7123456789:AAEabcdefghijklmnopqrstuvwxyz123456`
5. Add bot to your chat/group/channel as admin

## Complete Integration Example

Here's a full example integrating prompts into a deployment pipeline:

```python
from fastapi import FastAPI, Request, HTTPException
import httpx
import hmac
import hashlib
import os

app = FastAPI()

# Configuration
PROMPT_API_URL = os.getenv("PROMPT_API_URL", "http://localhost:8100")
SIGNING_SECRET = os.getenv("CALLBACK_SIGNING_SECRET")

# Verify callback signature
def verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        SIGNING_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

# Step 1: Request approval before deployment
async def request_deployment_approval(environment: str, commit_sha: str) -> str:
    """Create a prompt and return prompt_id for tracking"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PROMPT_API_URL}/v1/prompts",
            json={
                "text": f"Deploy {commit_sha[:7]} to {environment}?",
                "options": ["Approve", "Reject"],
                "callback_url": "https://your-app.com/webhook/prompts",
                "correlation_id": f"deploy-{environment}-{commit_sha}",
                "ttl_sec": 3600  # 1 hour to respond
            }
        )
        result = response.json()
        return result["prompt_id"]

# Step 2: Receive approval callback
@app.post("/webhook/prompts")
async def deployment_approval_callback(request: Request):
    # Verify signature
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not verify_signature(body, signature):
        raise HTTPException(401, "Invalid signature")

    # Parse payload
    import json
    payload = json.loads(body)

    prompt_id = payload["prompt_id"]
    answer = payload["answer"]["selected_option"]
    correlation_id = payload["correlation_id"]

    print(f"Deployment approval received: {answer} (correlation: {correlation_id})")

    if answer == "Approve":
        # Extract environment and commit from correlation_id
        # Format: "deploy-{environment}-{commit_sha}"
        parts = correlation_id.split("-", 2)
        environment = parts[1]
        commit_sha = parts[2]

        # Trigger deployment
        await deploy_to_environment(environment, commit_sha)

        # Notify via Telegram
        await send_notification(f"Deployment to {environment} started!")
    else:
        await send_notification(f"Deployment rejected by user")

    return {"status": "ok"}

# Step 3: Trigger deployment
async def deploy_to_environment(environment: str, commit_sha: str):
    print(f"Deploying {commit_sha} to {environment}...")
    # Your deployment logic here
    pass

# Step 4: Send status notifications
async def send_notification(message: str):
    """Send notification without requiring response"""
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{PROMPT_API_URL}/v1/prompts",
            json={
                "text": message,
                "options": [],  # No buttons = notification only
                "ttl_sec": 60  # Short TTL since no response needed
            }
        )

# Usage in CI/CD pipeline
@app.post("/deploy/{environment}")
async def deploy_endpoint(environment: str, commit_sha: str):
    if environment == "production":
        # Require approval for production
        prompt_id = await request_deployment_approval(environment, commit_sha)
        return {
            "status": "approval_pending",
            "prompt_id": prompt_id,
            "message": "Waiting for Telegram approval"
        }
    else:
        # Auto-deploy to non-production
        await deploy_to_environment(environment, commit_sha)
        return {"status": "deployed"}
```

## Advanced Usage

### Polling for Status (Alternative to Callbacks)

If you can't expose a webhook endpoint, poll for status instead:

```python
import asyncio
import httpx

async def wait_for_prompt_answer(prompt_id: str, timeout_sec: int = 3600) -> dict:
    """Poll prompt status until answered or timeout"""
    start_time = asyncio.get_event_loop().time()

    async with httpx.AsyncClient() as client:
        while True:
            # Check if timeout reached
            if asyncio.get_event_loop().time() - start_time > timeout_sec:
                raise TimeoutError(f"Prompt {prompt_id} not answered within {timeout_sec}s")

            # Get prompt status
            response = await client.get(
                f"http://localhost:8100/v1/prompts/{prompt_id}"
            )
            prompt = response.json()

            # Check if answered
            if prompt["state"] == "ANSWERED":
                return prompt["answer"]

            # Wait before next check
            await asyncio.sleep(5)

# Usage
prompt_id = await create_prompt(...)
answer = await wait_for_prompt_answer(prompt_id)
print(f"User responded: {answer['selected_option']}")
```

### Handling Expiration

Prompts automatically expire after their TTL. Handle expired prompts:

```python
async def check_prompt_expiration(prompt_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8100/v1/prompts/{prompt_id}"
        )
        prompt = response.json()

        if prompt["state"] == "EXPIRED":
            print(f"Prompt {prompt_id} expired without answer")
            # Handle timeout scenario
            await handle_timeout()
        elif prompt["state"] == "ANSWERED":
            print(f"Prompt answered: {prompt['answer']}")
        else:
            print(f"Prompt still pending")
```

### Custom Button Layouts

For better UX, organize buttons strategically:

```json
{
  "text": "Select deployment environment",
  "options": ["Dev", "Staging", "Production", "Cancel"]
}
```

**Best Practices:**
- Limit to 3-4 buttons for clarity
- Put most common/safe option first
- Put destructive option last
- Use clear, action-oriented labels

### Correlation IDs for Tracking

Use correlation IDs to link prompts to your internal operations:

```python
deployment_id = "deploy-20250115-001"

await create_prompt(
    text="Approve deployment?",
    correlation_id=deployment_id
)

# Later, in callback:
# correlation_id links back to your deployment record
```

## Error Handling

### Common Errors

**1. Invalid Signature (401)**
```json
{
  "detail": "Invalid signature"
}
```
**Fix:** Verify `CALLBACK_SIGNING_SECRET` matches on both sides

**2. File Not Found (400)**
```json
{
  "error": "file_not_found",
  "message": "File not found: C:\\images\\test.png"
}
```
**Fix:** Verify file path exists on server

**3. Prompt Not Found (404)**
```json
{
  "detail": "not found"
}
```
**Fix:** Check prompt_id is correct (include `#` character)

**4. Failed to Post to Telegram (500)**
```json
{
  "detail": "Failed to post prompt to Telegram"
}
```
**Fix:**
- Verify bot token is valid
- Check bot is added to chat as admin
- Verify chat_id is correct

### Retry Logic

The API includes built-in retry for callbacks:
- 3 attempts with exponential backoff
- If all fail, logs error but doesn't block

Your callback should:
- Return 200 OK quickly (< 5 seconds)
- Process asynchronously if needed
- Return non-200 only for actual errors

## Testing

### Test Basic Prompt Flow

```bash
# 1. Create prompt
PROMPT_ID=$(curl -s -X POST http://localhost:8100/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Test prompt",
    "options": ["Yes", "No"]
  }' | jq -r '.prompt_id')

echo "Created prompt: $PROMPT_ID"

# 2. Check Telegram - click a button

# 3. Verify status
curl http://localhost:8100/v1/prompts/$PROMPT_ID | jq
```

### Test with Webhook.site

Use [webhook.site](https://webhook.site) to inspect callbacks without coding:

```bash
# Get unique URL from webhook.site
WEBHOOK_URL="https://webhook.site/YOUR-UNIQUE-ID"

# Create prompt with that callback
curl -X POST http://localhost:8100/v1/prompts \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"Test callback\",
    \"options\": [\"Yes\", \"No\"],
    \"callback_url\": \"$WEBHOOK_URL\"
  }"

# Answer in Telegram
# Check webhook.site for payload
```

### Test Signature Verification

```python
import hmac
import hashlib

def test_signature():
    secret = "your-secret"
    body = b'{"prompt_id":"#123"}'

    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    print(f"Expected signature: sha256={expected}")

test_signature()
```

## Performance Considerations

### Rate Limits

- Telegram bot API: ~30 messages/second per bot
- Database: Async PostgreSQL handles high concurrency well
- Callbacks: 5-second timeout, 3 retries

### Scalability

For single-user system (current design):
- No horizontal scaling needed
- Single database connection pool sufficient
- One bot instance handles all prompts

### Optimization Tips

1. **Use correlation IDs** for tracking instead of polling
2. **Set appropriate TTLs** - don't make them too long
3. **Batch notifications** - don't send hundreds of prompts at once
4. **Cache prompt status** on your side if polling frequently

## Security Best Practices

1. **Always verify signatures** on callbacks
2. **Use HTTPS** for callback URLs in production
3. **Store bot token** in environment variables, never in code
4. **Rotate signing secret** periodically
5. **Validate prompt inputs** before creating (sanitize text)
6. **Rate limit** your API endpoints if exposing publicly
7. **Monitor for abuse** - unusual prompt creation patterns

## FAQ

**Q: Can I use this for multiple Telegram chats?**
A: Yes, pass different `chat_id` in each request, or register multiple channels using the Channel Gateway feature.

**Q: What happens if my callback endpoint is down?**
A: The system retries 3 times with delays. If all fail, the error is logged. The prompt state remains ANSWERED in the database.

**Q: Can I cancel/delete a prompt?**
A: Not currently supported. Use short TTLs or edit the Telegram message directly via bot API.

**Q: How long are prompts stored?**
A: Indefinitely in database. Implement cleanup logic if needed: `DELETE FROM prompts WHERE created_at < NOW() - INTERVAL '30 days'`

**Q: Can I use this without callbacks?**
A: Yes, poll `GET /v1/prompts/{prompt_id}` or `GET /v1/prompts/pending` instead.

**Q: Does this work with Telegram groups/channels?**
A: Yes. Bot must be added as admin. Use negative chat IDs for groups/channels.

**Q: Can I customize the button appearance?**
A: Telegram's inline buttons have fixed styling. You can only customize the label text.

**Q: What's the maximum TTL?**
A: 7 days (604,800 seconds). Longer TTLs risk cluttering your chat history.

## Changelog

**v1.0.0** (2025-01-15)
- Initial release
- Prompt creation with button options
- Text response support via ID pattern
- HMAC-signed webhook callbacks
- Media support (URL, path, upload)
- TTL-based expiration
- Simple counter-based IDs (#123 format)

## Support

For issues or questions:
- Check API logs: `docker compose logs -f`
- Verify bot token and chat ID configuration
- Test with webhook.site to isolate callback issues
- Review this documentation for common patterns
