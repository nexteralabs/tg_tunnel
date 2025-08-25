from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List


class PromptIn(BaseModel):
    chat_id: str | int | None = Field(
        default=None, 
        description="Telegram chat ID (uses default if not provided)",
        examples=["-1002954473836", "123456789"]
    )
    text: str = Field(
        description="The prompt message to send",
        examples=["Do you approve this deployment to production?"]
    )
    media_url: Optional[str] = Field(
        default=None,
        description="Optional image URL to include with the prompt",
        examples=["https://i.imgur.com/abc123.jpg", "https://cdn.example.com/image.png"]
    )
    media_path: Optional[str] = Field(
        default=None,
        description="Optional local file path to image (server-side file)",
        examples=["C:\\images\\screenshot.png", "/home/user/image.jpg", "./temp/photo.png"]
    )
    options: Optional[List[str]] = Field(
        default=None,
        description="Button options for quick responses",
        examples=[["Approve", "Reject"], ["Yes", "No", "Maybe"]]
    )
    allow_text: bool = Field(
        default=False,
        description="Allow text responses via ID:prompt_id format"
    )
    callback_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for response notifications",
        examples=["https://your-app.com/webhook/prompts"]
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Your reference ID for this prompt",
        examples=["deploy-2024-001", "approval-request-456"]
    )
    ttl_sec: Optional[int] = Field(
        default=3600, 
        ge=0, 
        le=7 * 24 * 3600,
        description="Time-to-live in seconds (max 7 days)",
        examples=[3600, 7200, 86400]
    )


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
