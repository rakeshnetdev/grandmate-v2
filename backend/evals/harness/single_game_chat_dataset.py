"""Golden single-game-chat dataset loading (Phase 10, `evaluation-strategy.md`).

Schema per line: `scenario_id`, `question`, `headers` (PGN-style header dict), `moves`
(SAN, played from the standard start position), `opening` (`{eco, opening_name,
matched_ply}` or `null`), `evaluations` (one entry per ply: `classification`, `eval_cp`,
`eval_swing_cp`, `is_critical_moment`), and `reviewed_by` (`null` until a human
spot-checks it — same has-provenance-vs-is-reviewed distinction every other golden set
in this project uses).

**Why SAN move lists, not stored FEN/UCI/EPD.** Hand-authoring correct FEN strings for
every ply of every scenario is exactly the kind of error-prone busywork a computer should
do instead — `replay_moves` derives them mechanically via `python-chess`, the same
library `domain/games/parsing.py` uses for the real ingestion pipeline, so a scenario's
game data is guaranteed self-consistent (legal, correctly-sequenced) by construction
rather than by careful typing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess


@dataclass(frozen=True)
class ReplayedMove:
    ply: int
    san: str
    uci: str
    fen_before: str
    fen_after: str
    epd_after: str


def replay_moves(moves: list[str]) -> list[ReplayedMove]:
    """Play `moves` (SAN) from the standard start position, deriving the fields
    `GameMove` needs. Raises `chess.IllegalMoveError` on an inconsistent scenario —
    caught at dataset-authoring time, not silently producing a broken fixture."""
    board = chess.Board()
    replayed = []
    for ply, san in enumerate(moves):
        fen_before = board.fen()
        move = board.parse_san(san)
        uci = move.uci()
        board.push(move)
        replayed.append(
            ReplayedMove(
                ply=ply,
                san=san,
                uci=uci,
                fen_before=fen_before,
                fen_after=board.fen(),
                epd_after=board.epd(),
            )
        )
    return replayed


@dataclass(frozen=True)
class EvaluationFixture:
    ply: int
    classification: str
    eval_cp: int | None
    mate_in: int | None
    eval_swing_cp: int
    is_critical_moment: bool


@dataclass(frozen=True)
class OpeningFixture:
    eco: str
    opening_name: str
    matched_ply: int


@dataclass(frozen=True)
class SingleGameChatScenario:
    scenario_id: str
    question: str
    headers: dict[str, str]
    moves: list[str]
    evaluations: list[EvaluationFixture]
    opening: OpeningFixture | None
    reviewed_by: str | None


def load_single_game_chat_scenarios(path: Path) -> list[SingleGameChatScenario]:
    scenarios = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row: dict[str, Any] = json.loads(line)
            opening = row.get("opening")
            scenarios.append(
                SingleGameChatScenario(
                    scenario_id=row["scenario_id"],
                    question=row["question"],
                    headers=row["headers"],
                    moves=row["moves"],
                    evaluations=[EvaluationFixture(**e) for e in row["evaluations"]],
                    opening=OpeningFixture(**opening) if opening else None,
                    reviewed_by=row.get("reviewed_by"),
                )
            )
    return scenarios


__all__ = [
    "EvaluationFixture",
    "OpeningFixture",
    "ReplayedMove",
    "SingleGameChatScenario",
    "load_single_game_chat_scenarios",
    "replay_moves",
]
