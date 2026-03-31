"""Pydantic schemas for channels"""

from typing import Literal

from pydantic import BaseModel, Field


class ChannelRegisterIn(BaseModel):
    """Channel registration request"""

    channel_id: str = Field(..., description="Unique channel identifier")
    telegram_chat_id: str = Field(..., description="Telegram chat ID")
    bot_token: str = Field(..., description="Telegram bot token for this channel")
    callback_url: str | None = Field(
        None, description="Callback URL for message forwarding (required for MESSAGE channels)"
    )
    channel_type: Literal["MESSAGE", "PROMPT"] = Field(
        "MESSAGE", description="Channel type: MESSAGE or PROMPT"
    )


class ChannelSendIn(BaseModel):
    """Send message request (matches MVP reference exactly)"""

    channel_id: str = Field(..., description="Channel to send to")
    text: str = Field(..., description="Message text")


class ChannelOut(BaseModel):
    """Channel info response"""

    channel_id: str
    telegram_chat_id: str
