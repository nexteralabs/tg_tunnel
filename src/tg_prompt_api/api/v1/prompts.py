"""Prompt API endpoints"""

import json
from fastapi import APIRouter, HTTPException, File, UploadFile, Form

from ...core.db import get_conn
from ...services.prompts import models, schemas, service

router = APIRouter()


@router.post("/prompts", response_model=schemas.PromptOut)
async def create_prompt_endpoint(p: schemas.PromptIn):
    """Create a prompt with optional media URL or path."""
    try:
        prompt_id, row = await service.create_and_post_prompt(
            chat_id=p.chat_id,
            channel_id=p.channel_id,  # NEW parameter
            text=p.text,
            media_path=p.media_path,
            media_url=str(p.media_url) if p.media_url else None,
            options=p.options or [],
            allow_text=p.allow_text,
            callback_url=str(p.callback_url) if p.callback_url else None,
            correlation_id=p.correlation_id,
            ttl_sec=p.ttl_sec or 3600,
            media_file=None,  # No file upload in this endpoint
        )
        return schemas.PromptOut(
            prompt_id=prompt_id, chat_id=row["chat_id"], message_id=row["message_id"]
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(
            400, {"error": "file_not_found", "message": "The specified media file was not found."}
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.post("/prompts/upload", response_model=schemas.PromptOut)
async def create_prompt_with_upload(
    text: str = Form(..., description="The prompt message to send"),
    channel_id: str = Form(None, description="Channel to use (defaults to '__system_prompt__')"),
    chat_id: str = Form(None, description="DEPRECATED: Use channel_id instead"),
    options: str = Form(None, description='JSON array of button options, e.g. \'["Yes", "No"]\''),
    allow_text: bool = Form(False, description="Allow text responses via ID:prompt_id format"),
    callback_url: str = Form(None, description="Webhook URL for response notifications"),
    correlation_id: str = Form(None, description="Your reference ID for this prompt"),
    ttl_sec: int = Form(3600, description="Time-to-live in seconds"),
    media_url: str = Form(None, description="Optional image URL (alternative to file upload)"),
    file: UploadFile = File(None, description="Optional image file to upload"),
):
    """Create a prompt with optional file upload or media URL."""
    # Parse options if provided
    parsed_options: list[str] | None = None
    if options:
        try:
            parsed_options = json.loads(options)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON format for options")

    # Validate that only one media source is provided
    if file and media_url:
        raise HTTPException(400, "Cannot provide both file upload and media_url")

    # Use service layer to create and post
    try:
        prompt_id, row = await service.create_and_post_prompt(
            chat_id=chat_id,
            channel_id=channel_id,  # NEW parameter
            text=text,
            media_path=None,  # File uploads don't use media_path
            media_url=media_url,  # Store URL in DB if provided
            options=parsed_options or [],
            allow_text=allow_text,
            callback_url=callback_url,
            correlation_id=correlation_id,
            ttl_sec=ttl_sec,
            media_file=file,  # Pass UploadFile object if provided
        )

        return schemas.PromptOut(
            prompt_id=prompt_id, chat_id=row["chat_id"], message_id=row["message_id"]
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.get("/prompts/pending", response_model=list[schemas.PromptRow])
async def list_pending_prompts():
    """List all pending prompts."""
    rows: list[dict] = []
    async for aconn in get_conn():
        rows = await models.list_pending(aconn)
    return [schemas.PromptRow(**r) for r in rows]


@router.get("/prompts/{prompt_id}", response_model=schemas.PromptRow)
async def get_prompt_details(prompt_id: str):
    """Get prompt details by ID."""
    row = None
    async for aconn in get_conn():
        row = await models.get_prompt(aconn, prompt_id)
    if not row:
        raise HTTPException(404, "not found")
    return schemas.PromptRow(**row)
