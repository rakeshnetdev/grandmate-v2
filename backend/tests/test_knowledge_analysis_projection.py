"""`AnalysisProjectionService` integration tests: real transactional `db_session`, real
Phase 4-6 model rows (opening match, move evaluations, motif/theme findings) — covers
what each finding type projects to, and idempotent re-projection.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AnalysisKnowledgeChunk,
    Game,
    GameAnalysis,
    GameColor,
    GameSource,
    MotifFinding,
    MotifType,
    MoveClassification,
    MoveEvaluation,
    OpeningMatch,
    Profile,
    ProfileKind,
    StrategicThemeFinding,
    StrategicThemeType,
    User,
)
from app.domain.knowledge.analysis_projection import AnalysisProjectionService
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


async def _make_full_analysis(session: AsyncSession, game: Game) -> GameAnalysis:
    """One opening match, one blunder move, one motif, and one theme -- exercises all
    four projection paths in a single game."""
    session.add(
        OpeningMatch(game_id=game.id, eco="C60", opening_name="Ruy Lopez", epd="fen", matched_ply=4)
    )

    analysis = GameAnalysis(game_id=game.id, analysis_version="test", engine_depth=12, summary={})
    session.add(analysis)
    await session.flush()

    session.add(
        MoveEvaluation(
            game_analysis_id=analysis.id,
            ply=10,
            eval_cp=-300,
            mate_in=None,
            best_move_uci="e2e4",
            pv=[],
            classification=MoveClassification.BLUNDER,
            eval_swing_cp=300,
            mate_swing=False,
            is_critical_moment=True,
            deep_analyzed=True,
        )
    )
    session.add(
        MoveEvaluation(
            game_analysis_id=analysis.id,
            ply=11,
            eval_cp=-290,
            mate_in=None,
            best_move_uci="d7d5",
            pv=[],
            classification=MoveClassification.BEST,
            eval_swing_cp=0,
            is_critical_moment=False,
            deep_analyzed=False,
        )
    )
    session.add(
        MotifFinding(
            game_analysis_id=analysis.id,
            ply=10,
            side=GameColor.WHITE,
            motif=MotifType.HANGING_PIECE,
            confidence=0.9,
            evidence={},
        )
    )
    session.add(
        StrategicThemeFinding(
            game_analysis_id=analysis.id,
            ply=8,
            side=GameColor.BLACK,
            theme=StrategicThemeType.WEAK_KING_SAFETY,
            confidence=0.75,
            evidence={},
        )
    )
    await session.flush()
    return analysis


class TestProjectGame:
    async def test_projects_opening_critical_moment_motif_and_theme(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, profile)
        await _make_full_analysis(db_session, game)

        service = AnalysisProjectionService(db_session, FakeEmbeddingProvider())
        rows = await service.project_game(game.id)

        kinds = {row.kind for row in rows}
        assert kinds == {"opening", "critical_moment", "motif", "theme"}
        assert all(row.profile_id == profile.id for row in rows)
        assert all(row.game_id == game.id for row in rows)

        opening_row = next(row for row in rows if row.kind == "opening")
        assert "Ruy Lopez" in opening_row.content
        assert opening_row.chunk_metadata["eco"] == "C60"

    async def test_the_non_critical_best_move_is_not_projected(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, profile)
        await _make_full_analysis(db_session, game)

        service = AnalysisProjectionService(db_session, FakeEmbeddingProvider())
        rows = await service.project_game(game.id)

        critical_moments = [row for row in rows if row.kind == "critical_moment"]
        assert len(critical_moments) == 1
        assert "ply 10" in critical_moments[0].content

    async def test_reprojecting_replaces_rather_than_duplicates(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, profile)
        await _make_full_analysis(db_session, game)
        service = AnalysisProjectionService(db_session, FakeEmbeddingProvider())
        await service.project_game(game.id)

        rows = await service.project_game(game.id)

        assert len(rows) == 4
        all_rows = (
            (
                await db_session.execute(
                    select(AnalysisKnowledgeChunk).where(AnalysisKnowledgeChunk.game_id == game.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(all_rows) == 4

    async def test_a_mate_swing_critical_moment_never_projects_a_bogus_centipawn_number(
        self, db_session: AsyncSession
    ) -> None:
        """Regression test: the RAG `analysis` bucket must never embed the mate-score
        classification sentinel as if it were a real centipawn swing — it would then be
        retrievable and citable to a user verbatim."""
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, profile)
        analysis = GameAnalysis(
            game_id=game.id, analysis_version="test", engine_depth=12, summary={}
        )
        db_session.add(analysis)
        await db_session.flush()
        db_session.add(
            MoveEvaluation(
                game_analysis_id=analysis.id,
                ply=19,
                eval_cp=None,
                mate_in=None,
                best_move_uci="e2e4",
                pv=[],
                classification=MoveClassification.BLUNDER,
                eval_swing_cp=99_470,
                mate_swing=True,
                is_critical_moment=True,
                deep_analyzed=False,
            )
        )
        await db_session.flush()

        service = AnalysisProjectionService(db_session, FakeEmbeddingProvider())
        rows = await service.project_game(game.id)

        critical_moment = next(row for row in rows if row.kind == "critical_moment")
        assert "99470" not in critical_moment.content
        assert "forced mate" in critical_moment.content
        assert critical_moment.chunk_metadata["mate_swing"] is True
        assert critical_moment.chunk_metadata["eval_swing_cp"] is None

    async def test_a_game_with_no_analysis_yet_projects_nothing(
        self, db_session: AsyncSession
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, profile)

        service = AnalysisProjectionService(db_session, FakeEmbeddingProvider())
        rows = await service.project_game(game.id)

        assert rows == []

    async def test_an_unknown_game_id_projects_nothing(self, db_session: AsyncSession) -> None:
        service = AnalysisProjectionService(db_session, FakeEmbeddingProvider())

        rows = await service.project_game(uuid.uuid4())

        assert rows == []
