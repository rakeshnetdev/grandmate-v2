"""The chat agent's tools (Phase 10, ADR-0008 §"the tool set", ADR-0010).

Each tool wraps an existing profile-scoped query or service — these tests check the
wrapping (profile scoping honoured, not-found handled, JSON-schema-shaped errors) rather
than re-testing the underlying query logic those modules already cover.
"""

from __future__ import annotations

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
from app.domain.patterns import OpeningEntry, OpeningIndex
from app.integrations.llm import build_embedding_provider
from app.orchestration.tools import ToolContext
from app.orchestration.tools.analysis_tools import (
    get_game_analysis,
    get_profile_aggregate,
    list_critical_moments,
    lookup_opening,
)
from app.orchestration.tools.knowledge_tools import search_knowledge
from app.orchestration.tools.validation_tools import validate_line

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


async def _seed_game(session: AsyncSession, profile: Profile, *, critical: bool) -> Game:
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
            eval_cp=-320 if critical else 30,
            mate_in=None,
            best_move_uci="e2e4",
            pv=["e2e4"],
            classification=MoveClassification.BLUNDER if critical else MoveClassification.BEST,
            eval_swing_cp=320 if critical else 0,
            is_critical_moment=critical,
        )
    )
    await session.flush()
    return game


def _ctx(
    session: AsyncSession, profile_id: uuid.UUID, *, opening_index: OpeningIndex | None = None
) -> ToolContext:
    settings = Settings()
    return ToolContext(
        session=session,
        profile_id=profile_id,
        settings=settings,
        embedding_provider=build_embedding_provider(settings.llm, settings.retrieval),
        opening_index=opening_index or OpeningIndex({}),
    )


class TestGetGameAnalysis:
    async def test_returns_moves_with_san_attached(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile, critical=False)

        result = await get_game_analysis(_ctx(db_session, profile.id), game_id=str(game.id))

        assert result["opening"] is None
        assert result["moves"] == [
            {
                "ply": 0,
                "san": "e4",
                "classification": "best",
                "eval_cp": 30,
                "mate_in": None,
                "eval_swing_cp": 0,
                "best_move_uci": "e2e4",
            }
        ]

    async def test_includes_the_opening_when_one_was_matched(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile, critical=False)
        db_session.add(
            OpeningMatch(
                game_id=game.id, eco="C50", opening_name="Italian Game", epd="x", matched_ply=0
            )
        )
        await db_session.flush()

        result = await get_game_analysis(_ctx(db_session, profile.id), game_id=str(game.id))

        assert result["opening"] == {"eco": "C50", "opening_name": "Italian Game"}

    async def test_a_game_owned_by_another_profile_is_not_found(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_profile(db_session)
        game = await _seed_game(db_session, owner, critical=False)
        other = await _make_profile(db_session)

        result = await get_game_analysis(_ctx(db_session, other.id), game_id=str(game.id))

        assert "error" in result

    async def test_an_invalid_game_id_is_reported_not_raised(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)

        result = await get_game_analysis(_ctx(db_session, profile.id), game_id="not-a-uuid")

        assert "error" in result


class TestListCriticalMoments:
    async def test_only_critical_plies_are_returned(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile, critical=True)

        result = await list_critical_moments(_ctx(db_session, profile.id), game_id=str(game.id))

        assert len(result["critical_moments"]) == 1
        assert result["critical_moments"][0]["ply"] == 0

    async def test_no_critical_plies_gives_an_empty_list(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        game = await _seed_game(db_session, profile, critical=False)

        result = await list_critical_moments(_ctx(db_session, profile.id), game_id=str(game.id))

        assert result["critical_moments"] == []


class TestGetProfileAggregate:
    async def test_rejects_a_window_outside_the_configured_set(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)

        result = await get_profile_aggregate(_ctx(db_session, profile.id), window=7)

        assert "error" in result

    async def test_a_default_window_computes_an_empty_but_valid_snapshot(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)

        result = await get_profile_aggregate(_ctx(db_session, profile.id))

        assert result["games_included"] == 0
        assert result["sufficient_sample"] is False


class TestLookupOpening:
    async def test_a_known_epd_returns_its_eco_and_name(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)
        index = OpeningIndex({"epd-1": OpeningEntry(eco="C50", name="Italian Game", epd="epd-1")})

        result = await lookup_opening(
            _ctx(db_session, profile.id, opening_index=index), epd="epd-1"
        )

        assert result["result"] == {"eco": "C50", "opening_name": "Italian Game", "epd": "epd-1"}

    async def test_an_unknown_epd_returns_no_result(self, db_session: AsyncSession) -> None:
        profile = await _make_profile(db_session)

        result = await lookup_opening(_ctx(db_session, profile.id), epd="unknown")

        assert result["result"] is None


class TestSearchKnowledge:
    async def test_an_unknown_bucket_is_rejected_before_any_retrieval_call(
        self, db_session: AsyncSession
    ) -> None:
        """No `OPENAI_API_KEY` is configured in tests (hermetic settings) — reaching the
        embedding call would raise. Getting a clean `{"error": ...}` back instead proves
        bucket validation happens first."""
        profile = await _make_profile(db_session)

        result = await search_knowledge(
            _ctx(db_session, profile.id), bucket="not-a-bucket", query="castling"
        )

        assert "error" in result


class TestValidateLine:
    def test_a_legal_line_is_legal(self) -> None:
        result = validate_line(fen=_START_FEN, moves=["e4", "e5"])

        assert result == {"legal": True, "illegal_at": None, "reason": None}

    def test_an_illegal_move_reports_its_index(self) -> None:
        result = validate_line(fen=_START_FEN, moves=["e4", "e4"])

        assert result["legal"] is False
        assert result["illegal_at"] == 1

    def test_an_invalid_fen_is_reported_not_raised(self) -> None:
        result = validate_line(fen="not a fen", moves=["e4"])

        assert result["legal"] is False
        assert result["illegal_at"] is None
