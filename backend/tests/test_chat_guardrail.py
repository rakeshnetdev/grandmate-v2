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
from app.db.models import (
    Game,
    GameAnalysis,
    GameMove,
    GameSource,
    MoveClassification,
    MoveEvaluation,
    OpeningMatch,
    Profile,
    ProfileKind,
    User,
)
from app.domain.chat.guardrail import validate_answer
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
