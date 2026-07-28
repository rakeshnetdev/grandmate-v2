"""Profile isolation for the `analysis` bucket (Phase 7, rag-architecture.md section 5,
claude.md rule 14): "a retrieval that crosses a profile boundary without an explicit
permission grant is a defect, not a feature." `AnalysisRetriever.search` takes
`profile_id` as a required keyword argument specifically so this cannot happen by
omission — these tests are the adversarial check that the enforcement actually holds,
not just the happy path.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import RetrievalSettings
from app.db.models import AnalysisKnowledgeChunk, Game, GameSource, Profile, ProfileKind, User
from app.domain.retrieval.analysis_retriever import AnalysisRetriever
from tests.fake_embeddings import FakeEmbeddingProvider


async def _make_profile(session: AsyncSession) -> Profile:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


async def _make_game(session: AsyncSession, profile: Profile) -> Game:
    game = Game(
        profile_id=profile.id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "A", "Black": "B"},
        raw_pgn_path=f"pgn/{profile.id}/test.pgn",
    )
    session.add(game)
    await session.flush()
    return game


async def _make_analysis_chunk(
    session: AsyncSession,
    profile: Profile,
    content: str,
    embedder: FakeEmbeddingProvider,
    *,
    kind: str = "critical_moment",
) -> None:
    game = await _make_game(session, profile)
    (embedding,) = await embedder.embed([content])
    session.add(
        AnalysisKnowledgeChunk(
            profile_id=profile.id,
            game_id=game.id,
            kind=kind,
            content=content,
            chunk_metadata={},
            embedding=embedding,
        )
    )
    await session.flush()


class TestAnalysisRetrieverIsolation:
    async def test_never_returns_another_profiles_chunks(self, db_session: AsyncSession) -> None:
        embedder = FakeEmbeddingProvider()
        owner = await _make_profile(db_session)
        other = await _make_profile(db_session)
        await _make_analysis_chunk(db_session, owner, "Owner's blunder at ply 20.", embedder)
        await _make_analysis_chunk(
            db_session, other, "Other profile's blunder at ply 20.", embedder
        )

        retriever = AnalysisRetriever(db_session, embedder, RetrievalSettings())
        results = await retriever.search("blunder at ply 20", profile_id=owner.id)

        assert len(results) == 1
        assert results[0].content == "Owner's blunder at ply 20."

    async def test_a_query_crafted_to_match_another_profiles_content_still_does_not_leak(
        self, db_session: AsyncSession
    ) -> None:
        """Not just the happy path: the query text is deliberately copied verbatim from
        the *other* profile's chunk, to check that similarity alone can never substitute
        for the profile_id filter."""
        embedder = FakeEmbeddingProvider()
        owner = await _make_profile(db_session)
        other = await _make_profile(db_session)
        secret_content = "Other profile's very specific hanging queen blunder on move 41."
        await _make_analysis_chunk(db_session, other, secret_content, embedder)

        retriever = AnalysisRetriever(db_session, embedder, RetrievalSettings())
        results = await retriever.search(secret_content, profile_id=owner.id)

        assert results == []

    async def test_empty_result_for_a_profile_with_no_analysis_chunks_yet(
        self, db_session: AsyncSession
    ) -> None:
        embedder = FakeEmbeddingProvider()
        owner = await _make_profile(db_session)
        other = await _make_profile(db_session)
        await _make_analysis_chunk(db_session, other, "Some content.", embedder)

        retriever = AnalysisRetriever(db_session, embedder, RetrievalSettings())
        results = await retriever.search("some content", profile_id=owner.id)

        assert results == []

    async def test_search_requires_profile_id_as_a_keyword_argument(
        self, db_session: AsyncSession
    ) -> None:
        """A structural check, not just a behavioural one: `profile_id` cannot be
        supplied positionally, which is what makes it impossible for a caller to forget
        or accidentally omit at a call site — see the module docstring."""
        embedder = FakeEmbeddingProvider()
        owner = await _make_profile(db_session)
        retriever = AnalysisRetriever(db_session, embedder, RetrievalSettings())

        try:
            await retriever.search("query", owner.id)  # type: ignore[call-arg]
        except TypeError:
            pass
        else:
            raise AssertionError("search() accepted profile_id positionally")

    async def test_finds_the_owners_own_chunks_the_happy_path(
        self, db_session: AsyncSession
    ) -> None:
        embedder = FakeEmbeddingProvider()
        owner = await _make_profile(db_session)
        await _make_analysis_chunk(
            db_session, owner, "Opening: Ruy Lopez, ECO C88.", embedder, kind="opening"
        )

        retriever = AnalysisRetriever(db_session, embedder, RetrievalSettings())
        results = await retriever.search("Ruy Lopez opening", profile_id=owner.id)

        assert len(results) == 1
        assert results[0].content == "Opening: Ruy Lopez, ECO C88."
