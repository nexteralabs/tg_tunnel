from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from ...core.db import fetchone, fetchall, execute

PENDING = "PENDING"
ANSWERED = "ANSWERED"
EXPIRED = "EXPIRED"


async def create_prompt(
    aconn,
    *,
    chat_id: str,
    text: str,
    media_url: str | None,
    options: list[str] | None,
    allow_text: bool,
    callback_url: str | None,
    correlation_id: str | None,
    ttl_sec: int | None,
) -> str:
    """Create a new prompt and return the simple formatted ID (e.g. '#123')"""
    expires_at = None
    if ttl_sec and ttl_sec > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_sec)

    # Generate a temporary UUID for the TEXT id column (keeping for compatibility)
    import uuid

    temp_id = str(uuid.uuid4())

    row = await fetchone(
        aconn,
        """
        INSERT INTO prompts (id, chat_id, text, media_url, options, allow_text, callback_url,
                             correlation_id, state, expires_at)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)
        RETURNING prompt_num
    """,
        temp_id,
        str(chat_id),
        text,
        media_url,
        json.dumps(options or []),
        allow_text,
        callback_url,
        correlation_id,
        PENDING,
        expires_at,
    )

    # Return the simple formatted ID
    return f"#{row['prompt_num']}"


async def add_option_map(aconn, prompt_id: str, option_id: str, label: str) -> None:
    """Add option mapping using simple prompt ID '#123' or legacy ID"""
    prompt_num = parse_prompt_id(prompt_id)
    if prompt_num:
        # Get the actual database ID from prompt_num
        prompt_row = await fetchone(aconn, "SELECT id FROM prompts WHERE prompt_num=%s", prompt_num)
        if not prompt_row:
            raise ValueError(f"Prompt not found: {prompt_id}")
        db_id = prompt_row["id"]
    else:
        # Fallback for legacy format
        db_id = prompt_id

    await execute(
        aconn,
        """
        INSERT INTO prompt_options(prompt_id, option_id, label) VALUES (%s,%s,%s)
    """,
        db_id,
        option_id,
        label,
    )


async def set_message_id(aconn, prompt_id: str, message_id: int) -> None:
    """Set message ID using simple prompt ID '#123' or legacy ID"""
    prompt_num = parse_prompt_id(prompt_id)
    if prompt_num:
        await execute(
            aconn, "UPDATE prompts SET message_id=%s WHERE prompt_num=%s", message_id, prompt_num
        )
    else:
        # Fallback for legacy format
        await execute(aconn, "UPDATE prompts SET message_id=%s WHERE id=%s", message_id, prompt_id)


async def list_pending(aconn) -> list[dict]:
    return await fetchall(
        aconn, "SELECT * FROM prompts WHERE state=%s ORDER BY created_at DESC", PENDING
    )


def parse_prompt_id(prompt_id: str) -> int | None:
    """Parse simple prompt ID format '#123' to integer"""
    if prompt_id.startswith("#"):
        try:
            return int(prompt_id[1:])
        except ValueError:
            return None
    # Try parsing as plain number (without #)
    if prompt_id.isdigit():
        return int(prompt_id)
    # Fallback for old format during transition
    return None


async def get_prompt(aconn, prompt_id: str) -> dict | None:
    """Get prompt by simple ID format '#123' or legacy ID"""
    prompt_num = parse_prompt_id(prompt_id)
    if prompt_num:
        return await fetchone(aconn, "SELECT * FROM prompts WHERE prompt_num=%s", prompt_num)
    else:
        # Fallback for legacy IDs
        return await fetchone(aconn, "SELECT * FROM prompts WHERE id=%s", prompt_id)


async def resolve_option_label(aconn, prompt_id: str, option_id: str) -> str | None:
    """Resolve option label by simple prompt ID '#123' or legacy ID"""
    prompt_num = parse_prompt_id(prompt_id)
    if prompt_num:
        # Get the actual database ID from prompt_num
        prompt_row = await fetchone(aconn, "SELECT id FROM prompts WHERE prompt_num=%s", prompt_num)
        if not prompt_row:
            return None
        db_id = prompt_row["id"]
    else:
        # Fallback for legacy format
        db_id = prompt_id

    row = await fetchone(
        aconn,
        "SELECT label FROM prompt_options WHERE prompt_id=%s AND option_id=%s",
        db_id,
        option_id,
    )
    return row["label"] if row else None


async def mark_answered(
    aconn,
    prompt_id: str,
    *,
    answer_type: str,
    value: str,
    user_id: int | None,
    username: str | None,
) -> None:
    """Mark prompt as answered using simple ID format '#123' or legacy ID"""
    prompt_num = parse_prompt_id(prompt_id)
    if prompt_num:
        # Use prompt_num for the query
        await execute(
            aconn,
            """
            UPDATE prompts
               SET state=%s,
                   answer=jsonb_build_object('type', %s::text, 'value', %s::text),
                   answered_by_id=%s,
                   answered_by_username=%s,
                   answered_at=now()
             WHERE prompt_num=%s AND state=%s
        """,
            ANSWERED,
            answer_type,
            value,
            user_id,
            username,
            prompt_num,
            PENDING,
        )
    else:
        # Fallback for legacy format
        await execute(
            aconn,
            """
            UPDATE prompts
               SET state=%s,
                   answer=jsonb_build_object('type', %s::text, 'value', %s::text),
                   answered_by_id=%s,
                   answered_by_username=%s,
                   answered_at=now()
             WHERE id=%s AND state=%s
        """,
            ANSWERED,
            answer_type,
            value,
            user_id,
            username,
            prompt_id,
            PENDING,
        )

    # Schedule callback notification as background task (don't block Telegram response!)
    import asyncio

    prompt_data = await get_prompt(aconn, prompt_id)
    if prompt_data and prompt_data.get("callback_url"):

        async def _send_callback_background():
            try:
                from ...core.notifier import notify_callback

                callback_payload = {
                    "prompt_id": prompt_id,
                    "correlation_id": prompt_data.get("correlation_id"),
                    "text": prompt_data.get("text"),
                    "answer": {
                        "type": answer_type,
                        "value": value,
                        "user_id": user_id,
                        "username": username,
                    },
                    "answered_at": prompt_data.get("answered_at").isoformat()
                    if prompt_data.get("answered_at")
                    else None,
                }
                await notify_callback(prompt_data["callback_url"], callback_payload)
            except Exception as callback_error:
                print(f"Background callback failed: {callback_error}")

        # Fire and forget - don't wait for callback to complete
        asyncio.create_task(_send_callback_background())


async def expire_old(aconn) -> int:
    row = await fetchone(
        aconn,
        """
        WITH upd AS (
          UPDATE prompts SET state=%s
           WHERE state=%s AND expires_at IS NOT NULL AND now() > expires_at
           RETURNING 1
        ) SELECT count(*) AS c FROM upd
    """,
        EXPIRED,
        PENDING,
    )
    return (row or {}).get("c", 0)


async def set_message_map(aconn, prompt_id: str, message_id: int) -> None:
    await set_message_id(aconn, prompt_id, message_id)


async def clean_on_boot(aconn) -> None:
    await execute(aconn, "DELETE FROM prompts WHERE state=%s AND message_id IS NULL", PENDING)
