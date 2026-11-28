from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Locale = Literal["en", "ar", "fa"]


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locale: Locale = "en"


class PostMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Upper bound here is only a transport cap; the configured limit is enforced in the service.
    content: str = Field(min_length=1, max_length=8000)


class Turn(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    cards: list[dict[str, Any]] = Field(default_factory=list)
    guardrail: str | None = None
    created_at: datetime


class Session(BaseModel):
    id: str
    locale: Locale
    turn_count: int
    handoff_case_id: str | None = None
    assistant_available: bool
    max_message_chars: int
    created_at: datetime
    updated_at: datetime
    turns: list[Turn] = Field(default_factory=list)
