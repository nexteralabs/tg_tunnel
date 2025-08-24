import os
import asyncio
from fastapi import FastAPI, HTTPException
from .config import settings
from .db import get_conn
from .schemas import PromptIn, PromptOut, PromptRow
from .models import create_prompt, list_pending, get_prompt, clean_on_boot
from .telegram_bot import post_prompt_to_chat
from .util import ulid
from .security import setup_secure_logging

# Fix Windows event loop policy for psycopg
if os.name == 'nt':  # Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI(title="Telegram Prompt API")


@app.on_event("startup")
async def _startup():
    # Setup secure logging with token redaction
    setup_secure_logging()

    if settings.CLEAN_ON_BOOT:
        async for aconn in get_conn():
            await clean_on_boot(aconn)


@app.post("/v1/prompts", response_model=PromptOut)
async def create_prompt_api(p: PromptIn):
    target_chat = p.chat_id or settings.TELEGRAM_TARGET_CHAT_ID

    # Create prompt and get the simple ID format (e.g. "#123")
    async for aconn in get_conn():
        prompt_id = await create_prompt(
            aconn,
            chat_id=str(target_chat),
            text=p.text,
            media_url=str(p.media_url) if p.media_url else None,
            options=p.options or [],
            allow_text=p.allow_text,
            callback_url=str(p.callback_url) if p.callback_url else None,
            correlation_id=p.correlation_id,
            ttl_sec=p.ttl_sec or 3600,
        )

    await post_prompt_to_chat(
        prompt_id, p.text, str(p.media_url) if p.media_url else None, p.options or [], target_chat
    )

    async for aconn in get_conn():
        row = await get_prompt(aconn, prompt_id)
        if not row:
            raise HTTPException(500, "prompt missing after create")
    return PromptOut(prompt_id=prompt_id, chat_id=row["chat_id"], message_id=row["message_id"])


@app.get("/v1/prompts/pending", response_model=list[PromptRow])
async def list_pending_api():
    async for aconn in get_conn():
        rows = await list_pending(aconn)
    return [PromptRow(**r) for r in rows]


@app.get("/v1/prompts/{prompt_id}", response_model=PromptRow)
async def get_prompt_api(prompt_id: str):
    async for aconn in get_conn():
        row = await get_prompt(aconn, prompt_id)
    if not row:
        raise HTTPException(404, "not found")
    return PromptRow(**row)
