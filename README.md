# TG-Gateway

[![CI](https://github.com/NexteraLabs/tg_gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/NexteraLabs/tg_gateway/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**The human-in-the-loop backbone for AI agent fleets. Give every agent its own Telegram channel, let them ask questions with interactive buttons, attach images, route answers back via signed webhooks — all over plain HTTP, no webhook infrastructure, no polling code, no DevOps.**

---

## Why TG-Gateway?

Modern AI agents are powerful but isolated. They can plan, reason, and execute. But the moment they need a human decision, they're stuck. No clean way to pause, ask, and resume. No way to surface an alert with context. No dedicated channel per agent so conversations don't collide.

TG-Gateway is the missing piece. One self-hosted service that turns Telegram into a full **human-agent communication bus**:

- **Interactive decision gates** - send a question with up to 10 labeled buttons; your agent gets a signed webhook the instant a human taps one
- **Free-text mid-workflow input** — accept typed replies without long-running sockets or polling loops
- **Per-agent dedicated channels** — register unlimited bots, each with its own Telegram chat; finance-bot, ops-bot, support-bot all isolated and routed independently
- **Rich media prompts** — attach images by URL, file upload, or local path; give humans the full picture before they decide
- **Always-on bidirectional messaging** — agents send, humans reply, TG-Gateway forwards everything back to your callback URL with automatic retry
- **Signed callbacks** — every outbound webhook carries an HMAC-SHA256 signature so you know it came from TG-Gateway, not an attacker
- **Zero public endpoint required** — long-polling means it runs behind NAT, a firewall, or a laptop with no exposed port

The result: a clean **human-in-the-loop** pattern that works with any language, any framework, any orchestrator — in under 30 seconds.

```
                       ┌─────────────────────────────────────────┐
 Agent A  ─── HTTP ──► │                                         │ ──► 👤 Operator (buttons + image)
 Agent B  ─── HTTP ──► │                TG-Gateway                │ ──► 👤 On-call (free text)
 Agent C  ─── HTTP ──► │    (your self-hosted comms backbone)    │ ──► 👤 Manager (approval gate)
                       │                                         │
 Agent A  ◄─ webhook ─ │ signed callbacks · per-channel routing  │ ◄── tap / reply
 Agent B  ◄─ webhook ─ │ HMAC auth · auto-retry · long-poll      │
 Agent C  ◄─ webhook ─ │                                         │
                       └─────────────────────────────────────────┘
```

---

## What's inside

TG-Gateway ships two complementary APIs under one service:

### Prompt API - Ask, then act

Send an interactive prompt to Telegram. Your agent gets a signed webhook callback the moment a human responds by button tap or free text.

**Perfect for:** deployment approvals, anomaly escalations, agent clarification gates, multi-step workflow checkpoints.

### Channel Gateway, Always-on bidirectional messaging

Register a Telegram channel with a dedicated bot. TG-Gateway polls for new messages and forwards them to your callback URL. Your backend sends replies via HTTP. Multiple agents, multiple channels, each isolated.

**Perfect for:** AI assistant interfaces, on-call chat bots, multi-agent conversation routing, human-supervised pipelines.

---

## 30 seconds to your first prompt

```bash
# 1. Start the service (Docker)
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, DATABASE_URL, and secrets
docker compose up -d

# 2. Send a prompt — your agent asks a question
curl -X POST http://localhost:8100/v1/prompts \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Ready to deploy v2.4.1 to production?",
    "options": ["Deploy", "Cancel"],
    "callback_url": "https://your-agent.example.com/on_answer",
    "correlation_id": "deploy-v2.4.1"
  }'

# → {"prompt_id": "#1", "chat_id": "-100...", "message_id": 42}
```

The Telegram user sees the message with two buttons. The moment they tap **Deploy**, TG-Gateway POSTs to your `callback_url`:

```json
{
  "prompt_id": "#1",
  "correlation_id": "deploy-v2.4.1",
  "text": "Ready to deploy v2.4.1 to production?",
  "answer": {
    "type": "option",
    "value": "Deploy",
    "user_id": 123456789,
    "username": "alice"
  },
  "answered_at": "2026-03-31T18:00:00.000Z"
}
```

The callback is signed (`X-Signature: sha256=...`) so you can verify it came from TG-Gateway and not an attacker.

---

## Channel Gateway — Bidirectional agent channel

Give each AI assistant its own dedicated Telegram bot and channel:

```bash
# Register a channel for your finance assistant
curl -X POST http://localhost:8100/register-channel \
  -H 'Content-Type: application/json' \
  -d '{
    "channel_id": "finance-bot",
    "telegram_chat_id": "-1001234567890",
    "bot_token": "987654:XYZ...",
    "callback_url": "https://finance-agent.internal/on_message"
  }'

# Your agent sends a message
curl -X POST http://localhost:8100/send \
  -H 'Content-Type: application/json' \
  -d '{"channel_id": "finance-bot", "text": "Quarterly report is ready for review."}'
```

When the user replies in Telegram, TG-Gateway forwards it to your `callback_url`:

```json
{
  "type": "telegram.message.created",
  "channel_id": "finance-bot",
  "from": "alice",
  "text": "Looks good, go ahead and publish."
}
```

TG-Gateway handles all the long-polling internally — no public-facing webhook URL required.

---

## Key features

| Feature | Detail |
|---------|--------|
| **Interactive prompts** | Inline keyboard buttons + free-text replies (`ID:#123 answer`) |
| **Signed callbacks** | HMAC-SHA256 `X-Signature` header on every outbound webhook |
| **Multi-channel routing** | Unlimited channels, each with its own bot token |
| **Media support** | Attach images via URL, file upload, or local path |
| **Long polling** | No public webhook URL needed — runs behind NAT/firewall |
| **Auto-restore** | Polling resumes automatically on restart |
| **Prompt TTL** | Configurable expiry; pending prompts cleaned on boot |
| **Optional auth** | API key (`USE_AUTH=true`) for all endpoints |
| **Self-hosted** | Runs in Docker, single `docker compose up` |
| **PostgreSQL backend** | Durable prompt state, no data loss on restart |

---

## Architecture

```
                           TG-Gateway (port 8100)
                           ┌─────────────────────────────────────────┐
                           │                                         │
  POST /v1/prompts ───────►│  Prompt API     ──► Telegram Bot API    │
  GET  /v1/prompts/:id     │  (aiogram)       ◄── button callbacks   │
  GET  /v1/prompts/pending │                                         │
                           │                                         │
  POST /register-channel ─►│  Channel        ──► Telegram Bot API    │
  POST /send               │  Gateway         ◄── long poll loop     │
  GET  /channels           │  (per-channel                           │
  DEL  /channels/:id       │   asyncio task)                         │
                           │                                         │
                           │  PostgreSQL ──── prompts                │
                           │                 channels                │
                           │                 prompt_options          │
                           └─────────────────────────────────────────┘
```

Each `POST /register-channel` spawns a dedicated polling loop for that channel's bot. Channels are restored automatically on startup from the database.

---

## Installation

### Docker (recommended)

```bash
git clone https://github.com/NexteraLabs/tg_gateway.git tg-gateway
cd tg-gateway
cp .env.example .env
# Edit .env — see Configuration below
docker compose up -d
```

Check the logs:
```bash
docker compose logs -f
```

### Local development

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and a running PostgreSQL instance.

```bash
uv sync
cp .env.example .env   # configure DATABASE_URL
uv run prompt-cli init_db
uv run prompt-cli init_channels
uv run prompt-cli run_api --host 127.0.0.1 --port 8100
```

---

## Configuration

All configuration is via environment variables (or `.env` file).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | Default bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_TARGET_CHAT_ID` | ✅ | — | Default chat/group ID for the system prompt channel |
| `DATABASE_URL` | ✅ | — | PostgreSQL DSN (`postgresql+psycopg://user:pass@host/db`) |
| `CALLBACK_SIGNING_SECRET` | ✅ | — | Strong random string for HMAC signing of callbacks |
| `TELEGRAM_WEBHOOK_SECRET` | ✅ | — | Strong random string (required even in polling mode) |
| `USE_AUTH` | — | `false` | Set `true` to require `X-API-Key` on all endpoints |
| `API_KEY` | ✅ if USE_AUTH | — | API key value (required when `USE_AUTH=true`) |
| `MEDIA_ALLOWED_DIR` | — | unset | Restrict `media_path` to this directory; disables feature if unset |
| `MAX_MEDIA_SIZE_MB` | — | `2` | Maximum file size for `media_path` uploads |
| `CLEAN_ON_BOOT` | — | `true` | Delete unsent prompts (no `message_id`) on startup |
| `ENABLE_DOCS` | — | `false` | Expose `/docs`, `/redoc`, `/openapi.json` |
| `CHANNEL_CALLBACK_MAX_RETRIES` | — | `3` | Retry attempts for channel message delivery |
| `CHANNEL_CALLBACK_RETRY_DELAY` | — | `5` | Seconds between retry attempts |
| `CHANNEL_OFFLINE_NOTIFICATION` | — | `"Assistant offline..."` | Message sent to Telegram when all retries fail |

> **Security note:** `CALLBACK_SIGNING_SECRET` and `TELEGRAM_WEBHOOK_SECRET` must be set to strong unique values. TG-Gateway will **refuse to start** if either is left at the default placeholder.

---

## Verifying callback signatures

Every outbound webhook carries an `X-Signature` header. Verify it in your receiver:

```python
import hmac, hashlib

def verify_signature(body: bytes, header: str, secret: str) -> bool:
    expected = "sha256=" + hmac.digest(secret.encode(), body, hashlib.sha256).hex()
    return hmac.compare_digest(expected, header)

# In your webhook handler:
raw_body = await request.body()
if not verify_signature(raw_body, request.headers["X-Signature"], CALLBACK_SIGNING_SECRET):
    raise HTTPException(403, "Invalid signature")
```

---

## API reference

### Prompt API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/prompts` | Create and send a prompt (JSON body) |
| `POST` | `/v1/prompts/upload` | Create a prompt with a file attachment (multipart) |
| `GET` | `/v1/prompts/pending` | List all unanswered prompts |
| `GET` | `/v1/prompts/{id}` | Get a single prompt by ID (e.g. `%23123` for `#123`) |

**Prompt fields:**

| Field | Type | Description |
|-------|------|-------------|
| `text` | `string` | Message text (max 4096 chars) |
| `channel_id` | `string?` | Target channel (defaults to `__system_prompt__`) |
| `options` | `string[]?` | Button labels (max 10, each max 64 chars) |
| `allow_text` | `bool` | Accept `ID:#N answer` free-text replies |
| `callback_url` | `string?` | Webhook URL for the answer |
| `correlation_id` | `string?` | Your reference ID (returned in callback) |
| `ttl_sec` | `int` | Prompt lifetime in seconds (default 3600, max 7 days) |
| `media_url` | `string?` | Image URL to attach |
| `media_path` | `string?` | Server-side file path (requires `MEDIA_ALLOWED_DIR`) |

### Channel Gateway

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/register-channel` | Register a channel and start polling |
| `POST` | `/send` | Send a message via a channel's bot |
| `GET` | `/channels` | List active channels |
| `DELETE` | `/channels/{id}` | Stop polling and deactivate a channel |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Health check (always unauthenticated) |

---

## Use case examples

### Human-in-the-loop deployment gate

```python
import httpx

async def request_deploy_approval(version: str) -> bool:
    resp = httpx.post("http://tg-gateway:8100/v1/prompts", json={
        "text": f"Deploy {version} to production?",
        "options": ["Deploy ✅", "Cancel ❌"],
        "callback_url": "https://ci.internal/on_deploy_answer",
        "correlation_id": f"deploy-{version}",
        "ttl_sec": 1800,  # 30 minute window
    })
    prompt_id = resp.json()["prompt_id"]
    # Your webhook handler updates a DB record — agent polls or awaits it
    return await wait_for_answer(prompt_id)
```

### Multi-agent channel routing

```python
agents = {
    "finance":    {"channel_id": "finance-bot",    "bot_token": "TOKEN_A"},
    "operations": {"channel_id": "ops-bot",        "bot_token": "TOKEN_B"},
    "support":    {"channel_id": "support-bot",    "bot_token": "TOKEN_C"},
}

# Register each agent's dedicated channel once
for name, cfg in agents.items():
    httpx.post("http://tg-gateway:8100/register-channel", json={
        **cfg,
        "telegram_chat_id": CHAT_IDS[name],
        "callback_url": f"https://agents.internal/{name}/on_message",
    })
```

### Anomaly escalation with context

```python
httpx.post("http://tg-gateway:8100/v1/prompts", json={
    "text": (
        "🚨 <b>CPU spike detected</b> on api-prod-3\n"
        "Current: 94% | Avg: 23% | Duration: 8 min\n\n"
        "Action required:"
    ),
    "options": ["Scale up", "Restart pod", "Ignore for 1h"],
    "callback_url": "https://ops.internal/on_escalation",
    "correlation_id": "alert-cpu-api-prod-3",
    "ttl_sec": 600,
})
```

---

## Security

- **Callback signatures** — every outbound webhook is signed with HMAC-SHA256 (`X-Signature` header)
- **Optional API key auth** — enable `USE_AUTH=true` to require `X-API-Key` on all endpoints
- **SSRF protection** — `callback_url` validation rejects private/reserved IP addresses
- **Path traversal protection** — `media_path` is sandboxed to `MEDIA_ALLOWED_DIR`
- **Secret enforcement** — service refuses to start with default/placeholder secrets
- **Token redaction** — bot tokens and HMAC signatures are scrubbed from all logs
- **SecretStr handling** — bot tokens never appear in error messages or Pydantic validation output
- **Docs disabled by default** — `/docs` and `/openapi.json` are off unless `ENABLE_DOCS=true`

For vulnerability reports, see [SECURITY.md](.github/SECURITY.md) — do not open a public issue.

---

## Contributing

Contributions, bug reports, and feature requests are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, architecture guide, and PR checklist.

---

## License

[MIT](LICENSE) — Copyright © 2026 [Nextera Labs](https://github.com/NexteraLabs)
