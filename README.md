# Telegram Prompt API

Generic service to post prompts into Telegram (channel/group), collect replies (buttons or `ID:#123 reply text`), and notify callers.

## Quick start

```bash
poetry install
docker compose up -d
cp .env.example .env
poetry run prompt-cli init_db
# run in two terminals, or use run_all
poetry run prompt-cli run_api
poetry run prompt-cli run_bot
# or
poetry run prompt-cli run_all
```

## Long polling notes

This project defaults to **long polling** (no public URL needed). On bot startup we:
- **disable any existing webhook** and **drop pending updates**:
  ```python
  await bot.delete_webhook(drop_pending_updates=True)
  ```
- start polling with **explicit allowed updates**:
  ```python
  await dp.start_polling(bot, allowed_updates=["message","callback_query"])
  ```

## API

Create a prompt:
```bash
curl -X POST http://localhost:8100/v1/prompts \
  -H 'Content-Type: application/json' \
  -d '{
    "text":"Approve deployment?",
    "options":["Yes","No"],
    "correlation_id":"deploy-42"
  }'
```

List pending:
```bash
curl http://localhost:8100/v1/prompts/pending
```

Get by id:
```bash
curl http://localhost:8100/v1/prompts/#123
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
poetry run prompt-cli fresh_start
```

## Notes

- For **channels**, free-text replies require a **linked discussion group**. For a private, single-user workflow, a **supergroup** is simpler.
- The pattern `ID:#123 your text` is only acted upon by the bot; nothing else is parsed.
- For production, run API and bot as separate processes/containers and add logging/metrics.
