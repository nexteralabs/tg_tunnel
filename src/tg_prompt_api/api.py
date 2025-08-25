import os
import asyncio
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends
from fastapi.responses import JSONResponse
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
    # Debug logging
    print(f"Received request - media_url: {p.media_url}, media_path: {p.media_path}")
    
    # Validate that only one media source is provided (treat empty strings as None)
    has_media_url = bool(p.media_url and str(p.media_url).strip())
    has_media_path = bool(p.media_path and p.media_path.strip())
    
    print(f"Validation - has_media_url: {has_media_url}, has_media_path: {has_media_path}")
    
    if has_media_url and has_media_path:
        raise HTTPException(400, "Cannot provide both media_url and media_path")
    
    target_chat = p.chat_id or settings.TELEGRAM_TARGET_CHAT_ID

    # Determine what to pass to telegram
    media_to_send = None
    if has_media_url:
        media_to_send = str(p.media_url)
    elif has_media_path:
        # Validate file exists
        import os
        print(f"Checking file path: {p.media_path}")
        if not os.path.exists(p.media_path):
            error_msg = f"File not found: {p.media_path}"
            print(f"ERROR: {error_msg}")
            raise HTTPException(status_code=400, detail={"error": "file_not_found", "message": error_msg, "path": p.media_path})
        if not os.path.isfile(p.media_path):
            error_msg = f"Path is not a file: {p.media_path}"
            print(f"ERROR: {error_msg}")
            raise HTTPException(status_code=400, detail={"error": "not_a_file", "message": error_msg, "path": p.media_path})
        print(f"File validated successfully: {p.media_path}")
        media_to_send = p.media_path

    # Create prompt and get the simple ID format (e.g. "#123")
    async for aconn in get_conn():
        prompt_id = await create_prompt(
            aconn,
            chat_id=str(target_chat),
            text=p.text,
            media_url=str(p.media_url) if p.media_url else p.media_path,  # Store the source reference
            options=p.options or [],
            allow_text=p.allow_text,
            callback_url=str(p.callback_url) if p.callback_url else None,
            correlation_id=p.correlation_id,
            ttl_sec=p.ttl_sec or 3600,
        )

    await post_prompt_to_chat(
        prompt_id, p.text, media_to_send, p.options or [], target_chat
    )

    async for aconn in get_conn():
        row = await get_prompt(aconn, prompt_id)
        if not row:
            raise HTTPException(500, "prompt missing after create")
    return PromptOut(prompt_id=prompt_id, chat_id=row["chat_id"], message_id=row["message_id"])


@app.post("/v1/prompts/upload", response_model=PromptOut)
async def create_prompt_with_upload(
    text: str = Form(..., description="The prompt message to send"),
    chat_id: str = Form(None, description="Telegram chat ID (uses default if not provided)"),
    options: str = Form(None, description="JSON array of button options, e.g. '[\"Yes\", \"No\"]'"),
    allow_text: bool = Form(False, description="Allow text responses via ID:prompt_id format"),
    callback_url: str = Form(None, description="Webhook URL for response notifications"),
    correlation_id: str = Form(None, description="Your reference ID for this prompt"),
    ttl_sec: int = Form(3600, description="Time-to-live in seconds"),
    media_url: str = Form(None, description="Optional image URL (alternative to file upload)"),
    file: UploadFile = File(None, description="Optional image file to upload")
):
    """Create a prompt with optional file upload or media URL."""
    import json
    from typing import Optional, List
    
    # Parse options if provided
    parsed_options: Optional[List[str]] = None
    if options:
        try:
            parsed_options = json.loads(options)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON format for options")
    
    # Validate that only one media source is provided
    if file and media_url:
        raise HTTPException(400, "Cannot provide both file upload and media_url")
    
    target_chat = chat_id or settings.TELEGRAM_TARGET_CHAT_ID

    # Create prompt in database
    async for aconn in get_conn():
        prompt_id = await create_prompt(
            aconn,
            chat_id=str(target_chat),
            text=text,
            media_url=media_url,  # Will store URL or None for uploaded files
            options=parsed_options or [],
            allow_text=allow_text,
            callback_url=callback_url,
            correlation_id=correlation_id,
            ttl_sec=ttl_sec,
        )

    # Handle media - either URL or uploaded file
    media_to_send = media_url
    if file:
        # For uploaded files, we'll pass the file content directly to telegram
        media_to_send = file
    
    await post_prompt_to_chat(
        prompt_id, text, media_to_send, parsed_options or [], target_chat
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
