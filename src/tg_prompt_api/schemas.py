from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List


class PromptIn(BaseModel):
    chat_id: str | int | None = None
    text: str
    media_url: Optional[HttpUrl] = None
    options: Optional[List[str]] = None
    allow_text: bool = False
    callback_url: Optional[HttpUrl] = None
    correlation_id: Optional[str] = None
    ttl_sec: Optional[int] = Field(default=3600, ge=0, le=7 * 24 * 3600)


class PromptOut(BaseModel):
    prompt_id: str
    chat_id: str
    message_id: int


class PromptRow(BaseModel):
    id: str
    chat_id: str
    message_id: int | None
    text: str
    state: str
    created_at: str
    expires_at: str | None
    answer: dict | None
