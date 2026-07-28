"""`GET /dev/search` (Phase 7): manual retrieval testing ahead of Phase 10's real agent
tool. Same HTTP-layer conventions as `test_import_routes.py` — a real transactional
`db_session`, `get_db_session` overridden to hand it out, requests run via
`httpx.ASGITransport` rather than `TestClient`'s background thread.

`OpenAIEmbeddingProvider` is stubbed with the deterministic fake, same rationale as
`_stub_analysis_dispatch` in `test_import_routes.py`: this is an HTTP-contract test, not
a real-embedding-API test — real-embedding behaviour is what `evals/` covers.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.db import get_db_session
from app.core.config import Settings
from app.db.models import KnowledgeBucket, KnowledgeChunk, KnowledgeDocument
from app.main import create_app
from tests.fake_embeddings import FakeEmbeddingProvider


async def _make_chunk(session: AsyncSession, bucket: KnowledgeBucket, content: str) -> None:
    embedder = FakeEmbeddingProvider()
    document = KnowledgeDocument(
        bucket=bucket,
        title=content[:30],
        source="test",
        source_url=None,
        licence="original",
        retrieved_at=date(2026, 7, 27),
        content_hash=str(uuid.uuid4()),
    )
    session.add(document)
    await session.flush()
    (embedding,) = await embedder.embed([content])
    session.add(
        KnowledgeChunk(
            document_id=document.id,
            bucket=bucket,
            chunk_index=0,
            content=content,
            token_count=len(content.split()),
            chunk_metadata={"heading": content[:20]},
            embedding=embedding,
        )
    )
    await session.flush()


@pytest_asyncio.fixture
async def dev_search_client(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(
        "app.api.routes.dev.OpenAIEmbeddingProvider",
        lambda *args, **kwargs: FakeEmbeddingProvider(),
    )

    app = create_app(Settings())

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestDevSearch:
    async def test_hybrid_search_returns_matching_chunk(
        self, dev_search_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await _make_chunk(db_session, KnowledgeBucket.TACTICS, "A fork attacks two pieces.")
        await _make_chunk(db_session, KnowledgeBucket.TACTICS, "A pin immobilises a piece.")

        response = await dev_search_client.get(
            "/api/v1/dev/search", params={"bucket": "tactics", "query": "fork attacks pieces"}
        )

        assert response.status_code == 200
        results = response.json()
        assert results[0]["content"].startswith("A fork")
        assert results[0]["retrieved_by"] == "fused"

    async def test_sparse_strategy_does_not_need_the_embedding_provider(
        self, dev_search_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Three chunks, not one: classic BM25's IDF is exactly zero for a term present
        # in precisely half a corpus (log(1) == 0) — a single-document corpus hits that
        # boundary immediately. See test_retrieval_sparse.py for the same note.
        await _make_chunk(db_session, KnowledgeBucket.OPENINGS, "The Sicilian Defence is sharp.")
        await _make_chunk(db_session, KnowledgeBucket.OPENINGS, "The French Defence is solid.")
        await _make_chunk(db_session, KnowledgeBucket.OPENINGS, "The Caro-Kann Defence is calm.")

        response = await dev_search_client.get(
            "/api/v1/dev/search",
            params={"bucket": "openings", "query": "Sicilian", "strategy": "sparse"},
        )

        assert response.status_code == 200
        assert response.json()[0]["retrieved_by"] == "sparse"

    async def test_unknown_bucket_is_rejected(self, dev_search_client: httpx.AsyncClient) -> None:
        response = await dev_search_client.get(
            "/api/v1/dev/search", params={"bucket": "not-a-real-bucket", "query": "anything"}
        )

        assert response.status_code == 422

    async def test_unknown_strategy_is_rejected(self, dev_search_client: httpx.AsyncClient) -> None:
        response = await dev_search_client.get(
            "/api/v1/dev/search",
            params={"bucket": "tactics", "query": "anything", "strategy": "not-a-strategy"},
        )

        assert response.status_code == 422

    async def test_analysis_bucket_is_rejected(self, dev_search_client: httpx.AsyncClient) -> None:
        """The `analysis` bucket is profile-scoped and this route has no auth — see the
        route's own docstring for why it is deliberately excluded."""
        response = await dev_search_client.get(
            "/api/v1/dev/search", params={"bucket": "analysis", "query": "anything"}
        )

        assert response.status_code == 422

    async def test_absent_in_production(self, db_session: AsyncSession) -> None:
        settings = Settings()
        settings.app.app_env = "production"
        app = create_app(settings)

        async def _override_db_session() -> AsyncIterator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_db_session] = _override_db_session
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(
                "/api/v1/dev/search", params={"bucket": "tactics", "query": "anything"}
            )

        assert response.status_code == 404
