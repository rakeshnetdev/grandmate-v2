"""Chat request/response schemas (Phase 10)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import Persona


class CreateChatThreadRequest(BaseModel):
    active_game_id: uuid.UUID | None = None


class ChatThreadSummary(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    title: str | None
    active_game_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SendChatMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    persona: Persona = Persona.SELF_LEARNER


class ChatCitation(BaseModel):
    """Deliberately untyped beyond `kind` — a citation's other fields vary by kind (see
    `domain/chat/prompts.py`'s output-contract description), and this is a debugging/
    transparency view, not a contract callers should pattern-match on."""

    model_config = {"extra": "allow"}

    kind: str


class ChatTurnResponse(BaseModel):
    thread: ChatThreadSummary
    answer: str
    citations: list[ChatCitation]
    grounded: bool


class ChatMessageOut(BaseModel):
    role: str
    content: str


class ChatThreadHistory(BaseModel):
    thread: ChatThreadSummary
    messages: list[ChatMessageOut]


__all__ = [
    "ChatCitation",
    "ChatMessageOut",
    "ChatThreadHistory",
    "ChatThreadSummary",
    "ChatTurnResponse",
    "CreateChatThreadRequest",
    "SendChatMessageRequest",
]
