# MVP Next Iteration Plan

## Project Context
Personal bridge system for AI assistant validation workflows. Single-user system enabling external validation when direct system access isn't available.

## Current State Analysis
- ✅ Core functionality working (prompt creation, Telegram posting, response collection, callbacks)
- ✅ Clean architecture (API layer, bot layer, database layer)
- ✅ Simple deployment (Poetry + Docker Compose)
- ❌ Missing security for bot token handling
- ❌ No structured logging for debugging
- ❌ Zero test coverage
- ❌ Limited error handling and monitoring

## Critical Areas for MVP Next Iteration

### 1. Security Enhancement (HIGH PRIORITY)
**Problem**: Telegram bot token exposed in plain text environment variables
**Risk**: Token visible in logs, memory dumps, config files

**Implementation Plan**:
- Convert `TELEGRAM_BOT_TOKEN` to `SecretStr` in config.py
- Convert other sensitive fields (`CALLBACK_SIGNING_SECRET`, `TELEGRAM_WEBHOOK_SECRET`) to `SecretStr`  
- Add token validation on application startup
- Implement logging filter to redact tokens from logs
- Update .gitignore to exclude .env files

**Files to Modify**:
- `src/tg_prompt_api/config.py` - SecretStr implementation
- `src/tg_prompt_api/telegram_bot.py` - Use get_secret_value()
- `src/tg_prompt_api/util.py` - Use get_secret_value() for signing
- `.gitignore` - Add .env exclusions

### 2. Structured Logging (HIGH PRIORITY)
**Problem**: No structured logging makes debugging and monitoring difficult

**Implementation Plan**:
- Add structured logging with JSON formatting
- Implement request/response logging for API endpoints
- Add state change logging for prompt lifecycle
- Log bot interactions (messages received, callbacks processed)
- Add error logging with context
- Include token redaction filter

**Files to Create/Modify**:
- `src/tg_prompt_api/logging_config.py` - Centralized logging setup
- `src/tg_prompt_api/api.py` - Add request/response logging middleware
- `src/tg_prompt_api/telegram_bot.py` - Add interaction logging
- `src/tg_prompt_api/models.py` - Add state change logging
- `src/tg_prompt_api/notifier.py` - Add callback logging

### 3. Unit Test Coverage (HIGH PRIORITY)
**Problem**: Zero test coverage limits confidence in changes and debugging

**Implementation Plan**:
- Create test structure with pytest fixtures
- Test prompt lifecycle (create → post → answer → callback)
- Test database models and state transitions
- Test bot message parsing (ID:prompt_id patterns, button callbacks)
- Test API endpoints (creation, listing, retrieval)
- Test callback notification system
- Mock external dependencies (Telegram API, HTTP callbacks)

**Files to Create**:
- `tests/` directory structure
- `tests/conftest.py` - pytest fixtures and test database setup
- `tests/test_models.py` - Database model tests
- `tests/test_api.py` - FastAPI endpoint tests
- `tests/test_telegram_bot.py` - Bot interaction tests
- `tests/test_notifier.py` - Callback notification tests
- `tests/test_util.py` - Utility function tests

### 4. Enhanced Error Handling (MEDIUM PRIORITY)
**Problem**: Limited error recovery and monitoring

**Implementation Plan**:
- Add comprehensive exception handling to API endpoints
- Implement graceful bot error handling
- Add database connection retry logic
- Enhance callback failure handling
- Add health check endpoints
- Implement proper error responses

**Files to Modify**:
- `src/tg_prompt_api/api.py` - API error handling
- `src/tg_prompt_api/telegram_bot.py` - Bot error recovery
- `src/tg_prompt_api/db.py` - Connection retry logic
- `src/tg_prompt_api/notifier.py` - Enhanced callback error handling

## Implementation Roadmap

### Phase 1: Security Foundation (Week 1)
1. Implement SecretStr for sensitive configuration
2. Add token redaction logging filter
3. Update bot initialization to use secure token access
4. Add .gitignore updates

**Acceptance Criteria**:
- Tokens no longer visible in logs or tracebacks
- Application validates token format on startup
- All sensitive config uses SecretStr

### Phase 2: Observability (Week 2)
1. Implement structured logging configuration
2. Add request/response logging to API
3. Add state change logging to models
4. Add bot interaction logging
5. Add callback notification logging

**Acceptance Criteria**:
- All significant events are logged with structured JSON
- Logs include request IDs for tracing
- Error logs include full context
- Logs can be easily filtered and searched

### Phase 3: Test Coverage (Week 3)
1. Create test infrastructure and fixtures
2. Implement core workflow tests
3. Add database model tests
4. Add API endpoint tests
5. Add bot interaction tests

**Acceptance Criteria**:
- >80% test coverage on core functionality
- Tests can run in isolated environment
- Tests include both success and error scenarios
- CI/CD can run tests automatically

### Phase 4: Error Handling & Polish (Week 4)
1. Enhance API error handling
2. Improve bot error recovery
3. Add health check endpoints
4. Add database retry logic
5. Polish callback error handling

**Acceptance Criteria**:
- Graceful handling of common error scenarios
- Health checks provide system status
- Database connection issues don't crash application
- Failed callbacks are retried appropriately

## Technical Specifications

### Dependencies to Add
```toml
# Security
pydantic = "^2.9.0"  # Already present, will use SecretStr

# Logging
structlog = "^23.1.0"
python-json-logger = "^2.0.7"

# Testing
pytest-asyncio = "^0.21.1"
pytest-mock = "^3.11.1"
httpx = "^0.27.0"  # Already present for testing HTTP
```

### Environment Variables
```env
# Secure configuration
TELEGRAM_BOT_TOKEN=bot_token_here
CALLBACK_SIGNING_SECRET=signing_secret_here
TELEGRAM_WEBHOOK_SECRET=webhook_secret_here

# Logging configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Test Database Setup
- Use SQLite in-memory database for tests
- Create fixtures for common test scenarios
- Mock external APIs (Telegram, callback URLs)

## Success Metrics
- [ ] Zero token exposures in logs/tracebacks
- [ ] Structured logs for all significant events
- [ ] >80% test coverage on core functionality
- [ ] Graceful error handling for common failures
- [ ] Health checks provide meaningful status
- [ ] Documentation updated for new features

## Non-Goals (What NOT to Build)
- ❌ Multi-user authentication
- ❌ Horizontal scalability features
- ❌ Complex error recovery mechanisms
- ❌ Dead letter queues
- ❌ Webhook support (long polling by design)
- ❌ Rate limiting
- ❌ Advanced monitoring/metrics

## Risk Mitigation
- **Risk**: Breaking existing functionality during refactor
  - **Mitigation**: Implement tests first, then refactor incrementally
- **Risk**: Over-engineering for single-user case
  - **Mitigation**: Keep solutions simple and focused on debugging needs
- **Risk**: Security changes breaking deployment
  - **Mitigation**: Maintain backward compatibility with current .env approach

## Definition of Done
- All security enhancements implemented and verified
- Comprehensive structured logging in place
- Test coverage >80% with all tests passing
- Enhanced error handling covers common failure scenarios
- Documentation updated to reflect changes
- System runs reliably in current deployment environment