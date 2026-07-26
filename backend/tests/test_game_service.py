"""GameParsingService integration tests: real DB, real storage, real replay."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Game,
    GameColor,
    GameMove,
    GameSource,
    Profile,
    ProfileKind,
    ProfileSource,
    User,
)
from app.domain.games import GameParsingService
from app.integrations.storage import LocalStorage

GAME_TEXT = """[Event "Test"]
[White "DrNykterstein"]
[Black "Hikaru"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0
"""

BROKEN_TEXT = "not a real pgn"


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


async def _make_profile(session: AsyncSession) -> Profile:
    user = User()
    session.add(user)
    await session.flush()
    profile = Profile(owner_user_id=user.id, kind=ProfileKind.SELF, display_name="Me")
    session.add(profile)
    await session.flush()
    return profile


async def _make_game(
    session: AsyncSession, storage: LocalStorage, profile: Profile, text: str = GAME_TEXT
) -> Game:
    path = f"pgn/{profile.id}/test.pgn"
    await storage.put(path, text.encode("utf-8"))
    game = Game(
        profile_id=profile.id,
        source=GameSource.UPLOAD,
        content_hash="hash",
        headers={"White": "DrNykterstein", "Black": "Hikaru"},
        raw_pgn_path=path,
    )
    session.add(game)
    await session.flush()
    return game


class TestCanonicalize:
    async def test_persists_a_game_move_row_per_ply(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, storage, profile)
        service = GameParsingService(db_session, storage)

        await service.canonicalize(game)
        await db_session.flush()

        moves = (
            (await db_session.execute(select(GameMove).where(GameMove.game_id == game.id)))
            .scalars()
            .all()
        )
        assert len(moves) == 5
        assert [m.san for m in sorted(moves, key=lambda m: m.ply)] == [
            "e4",
            "e5",
            "Nf3",
            "Nc6",
            "Bb5",
        ]

    async def test_sets_canonicalized_at_on_success(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, storage, profile)
        service = GameParsingService(db_session, storage)

        await service.canonicalize(game)

        assert game.canonicalized_at is not None
        assert game.parse_error is None

    async def test_a_replay_failure_records_parse_error_without_raising(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        """The game stays imported — only its canonicalization status reflects the
        failure. This does not un-import anything Phase 3 already committed."""
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, storage, profile, text=BROKEN_TEXT)
        service = GameParsingService(db_session, storage)

        await service.canonicalize(game)  # must not raise

        assert game.canonicalized_at is None
        assert game.parse_error is not None
        assert game.parse_error["reason"] == "unparseable"

        moves = (
            (await db_session.execute(select(GameMove).where(GameMove.game_id == game.id)))
            .scalars()
            .all()
        )
        assert moves == []

    async def test_re_canonicalizing_replaces_stale_moves_without_a_conflict(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, storage, profile)
        service = GameParsingService(db_session, storage)

        await service.canonicalize(game)
        await db_session.flush()
        await service.canonicalize(game)  # must not raise a PK conflict
        await db_session.flush()

        moves = (
            (await db_session.execute(select(GameMove).where(GameMove.game_id == game.id)))
            .scalars()
            .all()
        )
        assert len(moves) == 5


class TestFocusResolution:
    async def test_resolves_focus_when_a_header_name_matches_a_linked_source(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        db_session.add(
            ProfileSource(
                profile_id=profile.id, source=GameSource.LICHESS, source_username="DrNykterstein"
            )
        )
        await db_session.flush()
        game = await _make_game(db_session, storage, profile)
        service = GameParsingService(db_session, storage)

        await service.canonicalize(game)

        assert game.focus_color == GameColor.WHITE
        assert game.opponent_name == "Hikaru"

    async def test_leaves_focus_null_when_no_source_is_linked(
        self, db_session: AsyncSession, storage: LocalStorage
    ) -> None:
        profile = await _make_profile(db_session)
        game = await _make_game(db_session, storage, profile)
        service = GameParsingService(db_session, storage)

        await service.canonicalize(game)

        assert game.focus_color is None
        assert game.opponent_name is None
