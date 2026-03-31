# Telegram Prompt & Channel Gateway

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/NexteraLabs/telegram_prompt_api/actions/workflows/ci.yml/badge.svg)](https://github.com/NexteraLabs/telegram_prompt_api/actions/workflows/ci.yml)

Two services in one:
1. **Prompt API**: Post prompts into Telegram (channel/group), collect replies (buttons or `ID:#123 reply text`), and notify callers.
2. **Channel Gateway**: Bidirectional messaging gateway for multiple AI assistants to communicate with Telegram channels via assigned bots.

## Quick start

### Local development
```bash
uv sync
cp .env.example .env       # edit DATABASE_URL to point to your Postgres
uv run prompt-cli init_db
uv run prompt-cli init_channels
uv run prompt-cli run_api
```

### Docker (production)
```bash
cp .env.example .env       # edit both DATABASE_URL and DATABASE_URL_FROM_CONTAINER
docker compose up -d
```

The container exposes port `8100`. Your `.env` needs two database URLs:
- `DATABASE_URL` — used for local dev (`localhost`)
- `DATABASE_URL_FROM_CONTAINER` — used inside the container (`host.docker.internal`)

## Channel Gateway

Register a channel and start polling:
```bash
curl -X POST http://localhost:8100/register-channel \
  -H 'Content-Type: application/json' \
  -d '{
    "channel_id": "finance_ai",
    "telegram_chat_id": "-1001234567890",
    "bot_token": "123456:ABCDEF...",
    "callback_url": "http://localhost:5001/on_telegram"
  }'
```

Send message to channel:
```bash
curl -X POST http://localhost:8100/send \
  -H 'Content-Type: application/json' \
  -d '{
    "channel_id": "finance_ai",
    "text": "Hello from AI assistant!"
  }'
```

List active channels:
```bash
curl http://localhost:8100/channels
uv run prompt-cli list_channels
```

**Features:**
- Idempotent registration (re-register safely)
- Per-channel polling with auto-restore on startup
- Callback retry logic (3 attempts, 5 sec delay)
- Offline notification when callback fails
- Multiple channels with dedicated bots

## Long polling notes

This project uses **long polling** by default (no public URL needed). Each registered channel runs an independent polling loop that calls Telegram's `getUpdates` with a 30-second timeout.

On startup, the server:
1. Registers the default prompt channel (`__system_prompt__`)
2. Restores polling for all previously active channels
3. Each channel's poller loop runs as an `asyncio.Task` in the background

To disable polling for a channel, use `DELETE /channels/{channel_id}`.

## Prompt API

Create a prompt:
```bash
curl -X POST http://localhost:8100/v1/prompts \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Approve deployment?",
    "options": ["Yes", "No"],
    "correlation_id": "deploy-42"
  }'
```

List pending:
```bash
curl http://localhost:8100/v1/prompts/pending
```

Get by id:
```bash
curl http://localhost:8100/v1/prompts/%23123
```

## Answering by text

In your Telegram group/channel (you as the only human):
```
ID:#123 ship it tonight
```

## Buttons

If you created with `options`, inline buttons appear; clicking records the choice.

## Callbacks to your system

Set `callback_url` in the POST; the service will POST back the answer as JSON, signed with `X-Signature: sha256=...` (HMAC with `CALLBACK_SIGNING_SECRET`). Retries via Tenacity.

## Cleaning test data

On boot you can set `CLEAN_ON_BOOT=true` and/or run:
```bash
uv run prompt-cli fresh_start
```

## Notes

- For **channels**, free-text replies require a **linked discussion group**. For a private, single-user workflow, a **supergroup** is simpler.
- The pattern `ID:#123 your text` is only acted upon by the bot; nothing else is parsed.
- For production, use `docker compose up -d` to run the API in a container.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, coding conventions, and the PR checklist.

For security issues, see [.github/SECURITY.md](.github/SECURITY.md) — do not open a public issue.

## License

[MIT](LICENSE) — Copyright (c) 2026 Nextera Labs
