# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

** RULES TO ALWAYS FOLLOW **
** APPLY EVERYTHING YOU READ HERE **

-- get full project knowledge.

Always make a full analysis and PLAN your next modification properly.

** NEVER implement extra features the user didnt ask without asking first **
** NEVER implement fallback mechanism with default values without being asked to do so **
** Fallback mechanism hide problems and make the application very hard to debug and maintain
** WINDOWS CONSTRAINT: Never use emojis in print() commands - they cause UnicodeEncodeError on Windows **


### Before Starting work
- Be critical, the user isn't always right
- Validate if the proposed Idea make sens or if there would be a better solution.
- Always in plan mode to make a plan
- After getting the plan make sure you write in to .claude/tasks/TASK_NAME.md
- The plan should be a detailed implementation plan and the reason behind them, as well as task broken down.
- Think like a Senior developer with Architecture and whole project goal in minds. ** DONT ** work like a junior developer doing lazy surface fixes without thinking of the impact of that modification on the rest of the application.
- If the task require external knowledge or certain package, also research to get latest knowledge (Use task tool for research)
- Don't over plan it, always think MVP
- Once you write the plan, ask the user to review it, do not continue until i approve the plan.

### While Implementing

** NEVER implement extra features the user didnt ask without asking first **
** NEVER implement fallback mechanism with default values without being asked to do so **
** Fallback mechanism hide problems and make the application very hard
** WINDOWS CONSTRAINT: Never use emojis in print() commands - they cause UnicodeEncodeError on Windows ** 
- you should update the plan as you work
- after you complete task in the plan, you should update and append detailed description of the change you made, so following tasks can be easily hand over to other engineers or agents.
- Think like a Senior developer with Architecture and whole project goal in minds. ** DONT ** work like a junior developer doing lazy surface fixes without thinking of the impact of that modification on the rest of the application.
- If you think adding a feature would be good, always go in plan mode to propose it. Never take the initiative to implement something that wasnt asked without validating first.
- 1. First understand the complete workflow
  2. Make minimal, targeted changes
  3. Tested each change individually
  4. Dont try to fix multiple things at once
- Always make meaningful unit tests to test new implemented features
- Run the unit test after code modification
- Run `ruff check` and `ruff format` after any code modifications
- properly test the new features before claiming it works.

## Development Commands

### Setup and Installation
```bash
poetry install
docker compose up -d
cp .env.example .env
poetry run prompt-cli init_db
```

### Running the Application
```bash
# Run API server (port 8100) - handles all polling (prompts + channels)
poetry run prompt-cli run_api

# Note: Old run_bot and run_all commands removed
# The API now handles all Telegram polling via the unified channel system
```

### Database Operations
```bash
# Initialize database schema
poetry run prompt-cli init_db

# Clean test data and reinitialize
poetry run prompt-cli fresh_start
```

### Code Quality
```bash
# Format and lint code
ruff check
ruff format

# Run tests
pytest
```

## Architecture Overview

This is a **Telegram Prompt & Channel Gateway** with two main services:

1. **Prompt API**: Posts prompts to Telegram chats, collects responses via buttons or text patterns, and notifies callers via callbacks
2. **Channel Gateway**: Bidirectional messaging gateway for multiple AI assistants to communicate with Telegram channels via assigned bots

### Core Components

**Infrastructure Layer** (`core/`):
- **config.py**: Pydantic settings with token validation
- **db.py**: PostgreSQL async connection pool
- **telegram_bot.py**: Multi-bot management, message sending utilities
- **security.py**: Token redaction for logs
- **util.py**: Signing, retry utilities
- **notifier.py**: Callback notifications

**Service Layer** (`services/`):
- **prompts/**: Prompt domain (models, schemas, service, handlers)
- **channels/**: Channel domain (models, schemas, service, poller)

**API Layer** (`api/`):
- **app.py**: FastAPI factory
- **v1/prompts.py**: Prompt REST endpoints
- **v1/channels.py**: Channel REST endpoints

**CLI** (`cli.py`): Typer-based commands for running services and migrations

### Key Patterns

#### Prompt Lifecycle
1. **Create** via REST API → stored in PostgreSQL with PENDING state
2. **Post** to Telegram chat with optional inline buttons
3. **Answer** via button click or text pattern `ID:prompt_id your response`  
4. **Callback** to external systems with signed webhooks (if configured)

#### Bot Response Handling
- **Button responses**: Captured via callback queries, buttons removed after selection
- **Text responses**: Parsed using regex pattern `ID:#123 response text` (simple counter format)
- **Message tracking**: Each prompt stores Telegram message_id for button management
- **Confirmation messages**: Visual distinction with ✅ Approved vs 🔴 Rejected styling

#### Database Schema

**Prompt Tables:**
- **prompts**: Main table with `id` (TEXT, legacy UUID) and `prompt_num` (SERIAL, simple counter)
- **prompt_options**: Maps button option_ids to display labels
- States: `PENDING` → `ANSWERED` | `EXPIRED`
- **ID Format**: Simple counter format `#123` (user-facing) backed by auto-incrementing `prompt_num`

**Channel Tables:**
- **channels**: Channel registrations with bot tokens, callback URLs, polling state
- Columns: `channel_id` (PK), `telegram_chat_id`, `bot_token`, `callback_url`, `last_update_id`, `is_active`

#### Channel Gateway Pattern
1. **Register** via `/register-channel` → stored in PostgreSQL, polling starts immediately
2. **Poll** Telegram using channel's bot → `getUpdates` with offset tracking
3. **Forward** messages to callback URL with retry logic (3 attempts, 5 sec delay)
4. **Notify** channel if callback offline after retries
5. **Send** messages via `/send` using channel's bot

### Configuration
Environment-based settings in `core/config.py`:
- `TELEGRAM_BOT_TOKEN`: Default bot token for prompts
- `TELEGRAM_TARGET_CHAT_ID`: Default chat for prompts
- `DATABASE_URL`: PostgreSQL connection string
- `CALLBACK_SIGNING_SECRET`: HMAC key for webhook signatures
- `CLEAN_ON_BOOT`: Auto-cleanup failed prompts on startup
- `CHANNEL_CALLBACK_MAX_RETRIES`: Callback retry attempts (default: 3)
- `CHANNEL_CALLBACK_RETRY_DELAY`: Delay between retries in seconds (default: 5)
- `CHANNEL_OFFLINE_NOTIFICATION`: Message sent when callback fails

### Development Notes
- Uses **long polling** by default (no webhook setup needed)
- Bot automatically disables webhooks and drops pending updates on startup
- Prompts support TTL-based expiration
- Callback notifications use Tenacity for retry logic
- **Simple counter IDs**: User-friendly format `#123` instead of complex ULIDs
- **Secure token handling**: Pydantic SecretStr for sensitive configuration
- **Windows compatibility**: Uses WindowsSelectorEventLoopPolicy for psycopg

## Project Context & Design Decisions

### Purpose
This is a **personal bridge system** for AI assistant validation workflows. When an assistant needs human approval for actions, it creates prompts via this API, posts them to Telegram, and receives responses back for decision-making.

### Design Philosophy
- **Single-user system**: No multi-tenancy, authentication, or user management
- **Personal use only**: No scalability or high-availability requirements
- **Bridge communication**: Enables external validation when direct system access isn't available
- **Long polling by design**: System cannot be reached by webhooks (network constraints)
- **Simple deployment**: Minimal infrastructure requirements

### What This System Does NOT Need
- ❌ Horizontal scalability (single user)
- ❌ API authentication (internal system)  
- ❌ Rate limiting (personal use)
- ❌ Complex error recovery mechanisms
- ❌ Dead letter queues (simple retry sufficient)
- ❌ Multiple bot processes (single instance appropriate)
- ❌ Webhook support (network constraints prevent this)

### Critical Areas That Need Attention

#### 1. Security Concerns ✅ COMPLETED
- **Telegram Bot Token Security**: ✅ Implemented SecretStr for secure token handling
  - ✅ Tokens redacted from logs with regex filtering
  - ✅ Proper .get_secret_value() usage throughout codebase
  - ✅ Token format validation in configuration

#### 2. Testing Coverage
- **Missing Unit Tests**: pytest configured but no test files present
  - **Need**: Core workflow tests (prompt creation, response handling, state transitions)
  - **Need**: Database model tests
  - **Need**: Bot message parsing tests

#### 3. Logging & Observability  
- **No Structured Logging**: Limited debugging capability
  - **Need**: Request/response logging
  - **Need**: State change tracking
  - **Need**: Error logging with context
  - **Need**: Bot interaction logging

### Architecture Strengths for Use Case
✅ **Clean separation**: API layer, bot layer, database layer
✅ **Flexible responses**: Button clicks + text patterns (`ID:#123 response`)
✅ **State management**: Clear PENDING → ANSWERED/EXPIRED transitions
✅ **TTL handling**: Automatic cleanup of stale prompts
✅ **Simple deployment**: Poetry + Docker Compose
✅ **Callback system**: HMAC-signed notifications to external systems
✅ **Long polling**: Reliable without webhook complexity
✅ **Simple IDs**: User-friendly `#123` format instead of complex UUIDs
✅ **Visual confirmations**: Clear approve/reject styling with emojis
✅ **Windows compatibility**: Proper event loop handling for development