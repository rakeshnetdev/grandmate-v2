"""One-shot corpus ingestion runner (Phase 7).

Idempotent — safe to re-run after adding or editing a corpus document
(`KnowledgeIngestionService` skips unchanged documents by content hash and replaces
changed ones, see its own docstring). Needs a real `OPENAI_API_KEY` in `.env` (real
embedding calls) and Postgres running.

Usage (from `backend/`):
    uv run python -m scripts.ingest_corpus
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.session import create_engine, create_session_factory, session_scope
from app.domain.knowledge import KnowledgeIngestionService
from app.integrations.llm import OpenAIEmbeddingProvider


async def main() -> None:
    settings = get_settings()
    embedding_provider = OpenAIEmbeddingProvider(settings.llm, settings.retrieval)
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    try:
        async with session_scope(session_factory) as session:
            service = KnowledgeIngestionService(session, settings.retrieval, embedding_provider)
            results = await service.ingest_corpus()
    finally:
        await engine.dispose()
        await embedding_provider.aclose()

    for result in results:
        status = (
            "unchanged, skipped" if result.skipped_unchanged else f"{result.chunks_written} chunks"
        )
        print(f"[{result.bucket.value}] {result.title}: {status}")
    print(f"\n{len(results)} document(s) processed.")


if __name__ == "__main__":
    asyncio.run(main())
