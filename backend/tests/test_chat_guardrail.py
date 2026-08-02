"""The grounding guardrail: every citation checked against deterministic analysis truth
(Phase 10, `rag-architecture.md` §6). The correctness-critical piece of the chat phase —
these tests seed real `GameMove`/`MoveEvaluation` rows and verify the guardrail actually
distinguishes a true citation from a false one, not just that it runs.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.base import utc_now
from app.db.models import (
    Game,
    GameAnalysis,
    GameMove,
    GameSource,
    KnowledgeBucket,
    KnowledgeChunk,
    KnowledgeDocument,
    MoveClassification,
    MoveEvaluation,
    OpeningMatch,
    Profile,
    ProfileKind,
    User,
)
from app.db.models.knowledge import EMBEDDING_DIMENSIONS
from app.domain.chat.guardrail import retrieved_chunk_ids, validate_answer
from app.domain.patterns import OpeningIndex
from app.integrations.llm import build_embedding_provider
from app.orchestration.tools import ToolContext

_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_AFTER_E4_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


async def _make_profile(session: AsyncSession) -> Profile:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


async def _seed_game(session: AsyncSession, profile: Profile) -> Game:
    game = Game(
        profile_id=profile.id,
        source=GameSource.UPLOAD,
        content_hash=str(uuid.uuid4()),
        headers={"White": "A", "Black": "B"},
        raw_pgn_path="pgn/test.pgn",
    )
    session.add(game)
    await session.flush()

    session.add(
        GameMove(
            game_id=game.id,
            ply=0,
            san="e4",
            uci="e2e4",
            fen_before=_START_FEN,
            fen_after=_AFTER_E4_FEN,
            epd_after=_AFTER_E4_FEN.rsplit(" ", 2)[0],
        )
    )

    analysis = GameAnalysis(game_id=game.id, analysis_version="v1", engine_depth=12, summary={})
    session.add(analysis)
    await session.flush()
    session.add(
        MoveEvaluation(
            game_analysis_id=analysis.id,
            ply=0,
            eval_cp=30,
            mate_in=None,
            best_move_uci="e2e4",
            pv=["e2e4"],
            classification=MoveClassification.BEST,
            eval_swing_cp=0,
        )
    )
    await session.flush()
    return game


def _ctx(session: AsyncSession, profile_id: uuid.UUID) -> ToolContext:
    settings = Settings()
    return ToolContext(
        session=session,
        profile_id=profile_id,
        settings=settings,
        embedding_provider=build_embedding_provider(settings.llm, settings.retrieval),
        opening_index=OpeningIndex({}),
    )


class TestParsing:
    async def test_rejects_invalid_json(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        parsed, violations = await validate_answer(_ctx(db_session, profile.id), "not json")

        assert parsed is None
        assert violations == ["response was not valid JSON"]

    async def test_rejects_a_response_missing_the_answer_field(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        parsed, violations = await validate_answer(
            _ctx(db_session, profile.id), json.dumps({"citations": []})
        )

        assert parsed is None
        assert violations

    async def test_no_citations_at_all_is_valid(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        parsed, violations = await validate_answer(
            _ctx(db_session, profile.id), json.dumps({"answer": "General advice.", "citations": []})
        )

        assert parsed is not None
        assert violations == []


class TestMoveCitations:
    async def test_a_true_move_citation_passes(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile)
        content = json.dumps(
            {
                "answer": "1.e4 opens the centre.",
                "citations": [{"kind": "move", "game_id": str(game.id), "ply": 0, "san": "e4"}],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert violations == []

    async def test_a_wrong_san_at_a_real_ply_fails(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile)
        content = json.dumps(
            {
                "answer": "1.d4 opens the centre.",
                "citations": [{"kind": "move", "game_id": str(game.id), "ply": 0, "san": "d4"}],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert len(violations) == 1
        assert "d4" in violations[0]

    async def test_a_ply_that_does_not_exist_fails(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile)
        content = json.dumps(
            {
                "answer": "...",
                "citations": [{"kind": "move", "game_id": str(game.id), "ply": 99, "san": "e4"}],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert len(violations) == 1

    async def test_a_game_the_profile_does_not_own_fails(self, db_session: AsyncSession) -> None:
        owner = await _make_profile(db_session)
        game = await _seed_game(db_session, owner)
        other = await _make_profile(db_session)
        content = json.dumps(
            {
                "answer": "...",
                "citations": [{"kind": "move", "game_id": str(game.id), "ply": 0, "san": "e4"}],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, other.id), content)

        assert len(violations) == 1


class TestEvaluationCitations:
    async def test_a_true_evaluation_passes(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile)
        content = json.dumps(
            {
                "answer": "Slightly better for White.",
                "citations": [
                    {"kind": "evaluation", "game_id": str(game.id), "ply": 0, "eval_cp": 30}
                ],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert violations == []

    async def test_a_wrong_eval_cp_fails(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile)
        content = json.dumps(
            {
                "answer": "Winning for White.",
                "citations": [
                    {"kind": "evaluation", "game_id": str(game.id), "ply": 0, "eval_cp": 900}
                ],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert len(violations) == 1


class TestOpeningCitations:
    async def test_a_true_opening_citation_passes(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile)
        db_session.add(
            OpeningMatch(
                game_id=game.id, eco="C50", opening_name="Italian Game", epd="x", matched_ply=0
            )
        )
        await db_session.flush()
        content = json.dumps(
            {
                "answer": "You played the Italian Game.",
                "citations": [
                    {
                        "kind": "opening",
                        "game_id": str(game.id),
                        "eco": "C50",
                        "opening_name": "Italian Game",
                    }
                ],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert violations == []

    async def test_a_wrong_opening_name_fails(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile)
        db_session.add(
            OpeningMatch(
                game_id=game.id, eco="C50", opening_name="Italian Game", epd="x", matched_ply=0
            )
        )
        await db_session.flush()
        content = json.dumps(
            {
                "answer": "You played the Sicilian.",
                "citations": [
                    {
                        "kind": "opening",
                        "game_id": str(game.id),
                        "eco": "B20",
                        "opening_name": "Sicilian Defence",
                    }
                ],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert len(violations) == 1

    async def test_no_opening_matched_for_the_game_fails(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile)
        content = json.dumps(
            {
                "answer": "You played the Italian Game.",
                "citations": [
                    {
                        "kind": "opening",
                        "game_id": str(game.id),
                        "eco": "C50",
                        "opening_name": "Italian Game",
                    }
                ],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert len(violations) == 1


class TestVariationCitations:
    async def test_a_legal_variation_passes(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        content = json.dumps(
            {
                "answer": "1.e4 e5 is also fine.",
                "citations": [{"kind": "variation", "fen": _START_FEN, "moves": ["e4", "e5"]}],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert violations == []

    async def test_an_illegal_variation_fails(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        content = json.dumps(
            {
                "answer": "1.e4 e5 is also fine.",
                "citations": [{"kind": "variation", "fen": _START_FEN, "moves": ["e4", "e4"]}],
            }
        )

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert len(violations) == 1


class TestMalformedCitations:
    async def test_an_unknown_kind_fails(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        content = json.dumps({"answer": "...", "citations": [{"kind": "vibes"}]})

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert len(violations) == 1

    async def test_a_non_object_citation_fails(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        content = json.dumps({"answer": "...", "citations": ["e4"]})

        _parsed, violations = await validate_answer(_ctx(db_session, profile.id), content)

        assert len(violations) == 1


async def _seed_corpus_chunk(session: AsyncSession) -> KnowledgeChunk:
    """One real corpus document and chunk, so a knowledge citation has something true to
    point at and a title to be enriched with."""
    document = KnowledgeDocument(
        bucket=KnowledgeBucket.OPENINGS,
        title="The French Defence",
        source="Wikipedia",
        source_url="https://en.wikipedia.org/wiki/French_Defence",
        licence="CC BY-SA 4.0",
        retrieved_at=utc_now(),
        content_hash=str(uuid.uuid4()),
    )
    session.add(document)
    await session.flush()

    chunk = KnowledgeChunk(
        document_id=document.id,
        bucket=KnowledgeBucket.OPENINGS,
        chunk_index=0,
        content="The French Defence begins 1.e4 e6.",
        token_count=9,
        chunk_metadata={},
        embedding=[0.0] * EMBEDDING_DIMENSIONS,
    )
    session.add(chunk)
    await session.flush()
    return chunk


class TestKnowledgeCitations:
    """Phase 20. A general-knowledge answer had no citable kind at all: every kind
    demanded a game_id, so the model borrowed the open game's — and the guardrail
    correctly rejected it, dropping a perfectly good answer to the fallback."""

    async def test_a_chunk_retrieved_this_turn_is_valid_and_gains_its_title(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        chunk = await _seed_corpus_chunk(db_session)
        response = json.dumps(
            {
                "answer": "The French Defence begins 1.e4 e6.",
                "citations": [{"kind": "knowledge", "chunk_id": str(chunk.id)}],
            }
        )

        parsed, violations = await validate_answer(
            _ctx(db_session, profile.id),
            response,
            retrieved_chunk_ids={str(chunk.id)},
        )

        assert violations == []
        # The model supplied only an id; the display fields are database truth.
        assert parsed is not None
        assert parsed["citations"][0]["title"] == "The French Defence"
        assert parsed["citations"][0]["source"] == "Wikipedia"

    async def test_a_real_chunk_not_retrieved_this_turn_is_rejected(
        self, db_session: AsyncSession
    ) -> None:
        """Existing in the corpus is not enough — that would let the model cite any real
        document for any claim."""
        profile = await _make_profile(db_session)
        chunk = await _seed_corpus_chunk(db_session)
        response = json.dumps(
            {
                "answer": "The French Defence begins 1.e4 e6.",
                "citations": [{"kind": "knowledge", "chunk_id": str(chunk.id)}],
            }
        )

        _parsed, violations = await validate_answer(
            _ctx(db_session, profile.id), response, retrieved_chunk_ids=set()
        )

        assert any("not returned by a retrieval tool" in v for v in violations)

    async def test_a_knowledge_citation_needs_a_chunk_id(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        response = json.dumps(
            {"answer": "...", "citations": [{"kind": "knowledge", "title": "made up"}]}
        )

        _parsed, violations = await validate_answer(
            _ctx(db_session, profile.id), response, retrieved_chunk_ids=set()
        )

        assert any("needs chunk_id" in v for v in violations)


class TestRetrievedChunkIds:
    def test_collects_ids_from_every_retrieval_result(self) -> None:
        context = [
            {
                "tool": "search_knowledge",
                "result": {"results": [{"chunk_id": "a"}, {"chunk_id": "b"}]},
            },
            {"tool": "search_analysis", "result": {"results": [{"chunk_id": "c"}]}},
        ]

        assert retrieved_chunk_ids(context) == {"a", "b", "c"}

    def test_ignores_tool_calls_that_returned_no_chunks(self) -> None:
        """A failed tool call and a non-retrieval tool must contribute nothing rather
        than raising."""
        context = [
            {"tool": "get_game_analysis", "result": {"summary": {}}},
            {"tool": "search_knowledge", "result": {"error": "unknown bucket"}},
            {"tool": "search_knowledge", "result": "not even a dict"},
        ]

        assert retrieved_chunk_ids(context) == set()
