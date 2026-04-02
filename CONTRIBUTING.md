# Contributing to tg-gateway

Thank you for your interest in contributing! This guide explains how to set up the project locally, report issues, and submit improvements.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/tg-gateway.git
   cd tg-gateway
   ```
3. Create a feature branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```

## Local Setup

Requires Python 3.11–3.12, [uv](https://docs.astral.sh/uv/), and a running PostgreSQL instance.

```bash
uv sync
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, DATABASE_URL, etc.
uv run prompt-cli init_db
uv run prompt-cli run_api
```

### With Docker

```bash
cp .env.example .env   # fill in DATABASE_URL_DOCKER for container networking
docker compose up -d
```

## Code Quality

Run these before opening a PR:

```bash
ruff check src/
ruff format src/
pytest
```

All three must pass (no errors, no formatter diffs, no test failures).

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add TTL override per-prompt
fix: handle expired prompts in callback retry
docs: update Channel Gateway section in README
chore: bump aiogram to 3.14
refactor: extract signing logic into util module
test: add unit tests for prompt state transitions
```

## Pull Request Checklist

Before submitting:

- [ ] `ruff check` passes with no errors
- [ ] `ruff format` produces no diffs
- [ ] `pytest` passes
- [ ] No hardcoded secrets or credentials
- [ ] `.env.example` updated if new config variables were added
- [ ] CHANGELOG.md updated under `[Unreleased]`

## Reporting Issues

Use the GitHub issue templates:

- **Bug report** — something broken in the API, CLI, channels, or prompts
- **Feature request** — suggest an improvement

For security issues, see [SECURITY.md](.github/SECURITY.md) — do not open a public issue.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](.github/CODE_OF_CONDUCT.md). By participating, you agree to uphold this code.
