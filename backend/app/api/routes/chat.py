"""Chat threads and turns (Phase 10).

Thin per the "routes delegate" rule: orchestration lives in `domain/chat/service.py`.
`profile_id` scoping follows `reports.py`/`analytics.py`'s exact pattern
(`ScopedProfileIdDep`, Phase 8b) — a thread belongs to whichever profile the caller is
currently viewing, self or a study profile, never another profile.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies.db import DbSessionDep
from app.api.dependencies.llm import EmbeddingProviderDep, LLMProviderDep
from app.api.dependencies.patterns import OpeningIndexDep
from app.api.dependencies.profile_scope import ScopedProfileIdDep
from app.api.dependencies.settings import SettingsDep
from app.db.models import ChatThread, Game
from app.domain.chat import ChatService, get_owned_thread
from app.schemas.chat import (
    ChatThreadHistory,
    ChatThreadSummary,
    ChatTurnResponse,
    CreateChatThreadRequest,
    SendChatMessageRequest,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _to_summary(thread: ChatThread) -> ChatThreadSummary:
    return ChatThreadSummary(
        id=thread.id,
        profile_id=thread.profile_id,
        title=thread.title,
        active_game_id=thread.active_game_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


def _build_service(
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    embedding_provider: EmbeddingProviderDep,
    opening_index: OpeningIndexDep,
) -> ChatService:
    return ChatService(session, settings, llm_provider, embedding_provider, opening_index)


@router.post("/threads", response_model=ChatThreadSummary, status_code=status.HTTP_201_CREATED)
async def create_thread(
    body: CreateChatThreadRequest,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    embedding_provider: EmbeddingProviderDep,
    opening_index: OpeningIndexDep,
) -> ChatThreadSummary:
    if body.active_game_id is not None:
        game = await session.get(Game, body.active_game_id)
        if game is None or game.profile_id != profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    service = _build_service(session, settings, llm_provider, embedding_provider, opening_index)
    thread = await service.create_thread(profile_id, active_game_id=body.active_game_id)
    return _to_summary(thread)


@router.get("/threads", response_model=list[ChatThreadSummary])
async def list_threads(
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    embedding_provider: EmbeddingProviderDep,
    opening_index: OpeningIndexDep,
) -> list[ChatThreadSummary]:
    service = _build_service(session, settings, llm_provider, embedding_provider, opening_index)
    threads = await service.list_threads(profile_id)
    return [_to_summary(t) for t in threads]


@router.get("/threads/{thread_id}", response_model=ChatThreadHistory)
async def get_thread_history(
    thread_id: uuid.UUID,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    embedding_provider: EmbeddingProviderDep,
    opening_index: OpeningIndexDep,
) -> ChatThreadHistory:
    thread = await get_owned_thread(session, thread_id, profile_id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    service = _build_service(session, settings, llm_provider, embedding_provider, opening_index)
    messages = await service.get_history(profile_id, thread_id)
    return ChatThreadHistory(thread=_to_summary(thread), messages=messages or [])


@router.post("/threads/{thread_id}/messages", response_model=ChatTurnResponse)
async def send_message(
    thread_id: uuid.UUID,
    body: SendChatMessageRequest,
    profile_id: ScopedProfileIdDep,
    session: DbSessionDep,
    settings: SettingsDep,
    llm_provider: LLMProviderDep,
    embedding_provider: EmbeddingProviderDep,
    opening_index: OpeningIndexDep,
) -> ChatTurnResponse:
    service = _build_service(session, settings, llm_provider, embedding_provider, opening_index)
    result = await service.send_message(profile_id, thread_id, body.persona, body.message)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    return ChatTurnResponse(
        thread=_to_summary(result.thread),
        answer=result.answer,
        citations=result.citations,
        grounded=result.grounded,
    )


__all__ = ["router"]
