# tg-gateway

## Project Configuration

- **Language:** Python 3.11+ (CI and Docker run on 3.12)
- **Framework:** FastAPI + uvicorn
- **Package manager:** `uv`
- **Test runner:** `uv run pytest`
- **Lint/format:** `uv run ruff check src/ && uv run ruff format src/`
- **Ticket system:** jira
- **Jira base URL:** https://ne-projects.atlassian.net

## Development Workflow

This project uses the codesmith workflow. Start any dev task by describing what you want to build — the workflow drives automatically through brainstorm → workspace → plan → implement → review → ship.

## Core Rules

- **Never implement features not explicitly asked for** — propose first, then implement
- **Never implement fallback mechanisms with default values** — they hide bugs and make debugging hard
- **No emojis in `print()` calls** — causes `UnicodeEncodeError` on Windows
- Make minimal, targeted changes — don't fix multiple things at once

## Workflow

1. Validate the idea — be critical, propose a better solution if one exists
2. Plan before implementing — think MVP, not over-engineered
3. Share the plan and **wait for approval** before writing code
4. Update the plan as you go with what was changed and why
5. Run `uv run ruff check src/` and `uv run ruff format src/` after any code changes
6. Run `uv run pytest` after any code changes

## Core Principles

### Plan Mode Default

Enter plan mode for any non-trivial task (3+ steps or architectural decisions). If something goes wrong, STOP and re-plan — don't keep pushing.

### Verification Before Done

Never mark a task complete without proving it works. Run tests, check logs, demonstrate correctness. Never say "should work" — prove it.

### Simplicity First

Make every change as simple as possible. Three clear lines beat a premature abstraction. No feature flags for hypotheticals. No helpers for one-time operations.

### No Laziness

Find root causes. Avoid temporary fixes. Maintain senior-level engineering standards.

## Task Management

1. Write the plan in `.claude/tasks/todo.md` with checkable items
2. Confirm the plan before implementation
3. Mark items complete as you go
4. Add a review section to `.claude/tasks/todo.md` when done

## Architecture

**Telegram Prompt & Channel Gateway** — two services in one API:

1. **Prompt API**: Post prompts to Telegram, collect button/text responses, notify callers via signed webhooks
2. **Channel Gateway**: Bidirectional messaging for AI agents to communicate with Telegram channels

### Structure

```
src/tg_gateway/
├── core/           # config, db, telegram_bot, security, notifier, util
├── services/
│   ├── prompts/    # models, schemas, service, handlers
│   └── channels/   # models, schemas, service, poller
├── api/
│   ├── app.py
│   └── v1/         # prompts.py, channels.py
└── cli.py          # Typer CLI
```

### Key Patterns

**Prompt lifecycle**: `PENDING` → `ANSWERED` | `EXPIRED`
- Created via REST, posted to Telegram with inline buttons
- Answered via button click or text pattern `ID:#123 response`
- Callback sent to caller via HMAC-signed webhook

**Channel lifecycle**:
- Register → start polling → forward messages to callback URL → send via `/send`
- 3 retry attempts with 5s delay on callback failure

### Configuration

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Default bot token for prompts |
| `TELEGRAM_TARGET_CHAT_ID` | Default chat for prompts |
| `DATABASE_URL` | PostgreSQL connection string |
| `CALLBACK_SIGNING_SECRET` | HMAC key for webhook signatures |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook verification secret |
| `CLEAN_ON_BOOT` | Auto-cleanup failed prompts on startup |
| `CHANNEL_CALLBACK_MAX_RETRIES` | Callback retry attempts (default: 3) |
| `CHANNEL_CALLBACK_RETRY_DELAY` | Delay between retries in seconds (default: 5) |

### Design Constraints

- **Single-user system** — no multi-tenancy, no auth, no rate limiting
- **Long polling by default** — webhooks optional
- **Simple IDs** — `#123` counter format (user-facing), UUID internally
- **Tokens as SecretStr** — redacted from logs via regex filter
