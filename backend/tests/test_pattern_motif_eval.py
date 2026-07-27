"""Phase 6 detector precision suite — the "motif precision/recall vs labelled set"
evaluation named in `project-plan.md`'s Phase 6 evaluation cadence.

Positive cases are real puzzles from the official Lichess puzzle database
(https://database.lichess.org/, CC0-licensed), individually hand-picked — two per motif,
retrieved 2026-07-26 via the public single-puzzle endpoint
(`GET https://lichess.org/api/puzzle/next?angle=<theme>`), not a bulk download of the
6-million-puzzle dump. Ground truth here is Lichess's own community-vetted theme tag,
which is independent of this codebase's detectors — that independence is what makes this
a real precision/recall check rather than the detector grading its own homework.

Each puzzle's `(fen_before, uci)` pair is the exact ply within that puzzle's real solution
line where the tagged motif is structurally created, worked out by replaying the puzzle's
game PGN to `initialPly` and then walking `solution` (see the phase report for the mapping
mechanics: Lichess's `Moves`/`solution` convention isn't quite the single before/after ply
shape our detectors take). `source` on each case is the puzzle's own training URL, for
anyone who wants to sanity-check the position by eye.

Negative cases are the same near-miss fixtures already unit-tested per detector in
`test_pattern_motifs.py` (one per motif) — reused here, not re-derived, so this file's job
is purely computing an aggregate precision/recall number across the whole taxonomy in one
place rather than re-litigating whether each detector's edge cases are individually
correct.
"""

from __future__ import annotations

import chess
import pytest

from app.core.config import PatternSettings
from app.db.models import MotifType
from app.domain.patterns.motifs.registry import MOTIF_DETECTORS

SETTINGS = PatternSettings()

# (motif, fen_before, uci, lichess puzzle URL) — real puzzles, ground truth from Lichess's
# own theme tag, not from this codebase.
POSITIVE_CASES: list[tuple[MotifType, str, str, str]] = [
    (
        MotifType.BACK_RANK_MATE,
        "bR2r1k1/5ppp/2p5/8/3Pp3/4P3/2r3PP/6K1 w - - 2 29",
        "b8e8",
        "https://lichess.org/training/0z3lT",
    ),
    (
        MotifType.BACK_RANK_MATE,
        "4r1k1/ppr2ppp/3p4/3P1q2/2P5/5N2/P4PPP/4R1K1 w - - 0 24",
        "e1e8",
        "https://lichess.org/training/iJWYW",
    ),
    (
        MotifType.REMOVING_THE_DEFENDER,
        "r1b1k2r/pp1p1ppp/6n1/2q4B/3N1b2/8/PP4PP/RN1Q1R1K w kq - 0 15",
        "h5g6",
        "https://lichess.org/training/3Nk5L",
    ),
    (
        MotifType.REMOVING_THE_DEFENDER,
        "2k5/1pprR2p/p7/3N2r1/P1P5/3b2P1/5P2/2R3K1 b - - 2 26",
        "g5d5",
        "https://lichess.org/training/XTtGe",
    ),
    (
        MotifType.DISCOVERED_ATTACK,
        "8/pp1b4/5k1p/3p3P/2p1p1P1/P1P1P2B/1P4K1/8 w - - 0 34",
        "g4g5",
        "https://lichess.org/training/cPe45",
    ),
    (
        MotifType.DISCOVERED_ATTACK,
        "3R4/p1p5/1p2pk2/4p3/4PP2/2Q2Rp1/PP5q/5K2 b - - 3 30",
        "g3g2",
        "https://lichess.org/training/rQIFH",
    ),
    (
        MotifType.DOUBLE_CHECK,
        "r4rk1/ppqn2p1/7p/3p4/2pPP3/2P1B1nP/PPBN2PK/R2QR3 b - - 0 21",
        "g3f1",
        "https://lichess.org/training/yCgRg",
    ),
    (
        MotifType.DOUBLE_CHECK,
        "3r4/5k1p/3P1p1B/6pn/2N4P/2b3P1/B4P1K/8 w - - 1 32",
        "c4e5",
        "https://lichess.org/training/DQabC",
    ),
    (
        MotifType.FORK,
        "6k1/p4p1p/5p2/7r/P4bN1/1r6/6PP/4R1K1 w - - 0 38",
        "g4f6",
        "https://lichess.org/training/zJ3YX",
    ),
    (
        MotifType.FORK,
        "6k1/5p2/8/7q/3nPQ2/6K1/PP4P1/5R2 b - - 3 30",
        "d4e2",
        "https://lichess.org/training/rm9RU",
    ),
    (
        MotifType.HANGING_PIECE,
        "r3k2r/pBp2ppp/3b1q2/8/2Q5/1P1p4/P1PP1P1P/R3K1R1 w Qkq - 0 15",
        "b7a8",
        "https://lichess.org/training/c04P8",
    ),
    (
        MotifType.HANGING_PIECE,
        "rnk4r/pbpp4/1p2pQ1q/6p1/3P4/2P2NP1/P1P2PP1/2KR1B2 w - - 0 18",
        "f6h6",
        "https://lichess.org/training/mvpPt",
    ),
    (
        MotifType.PIN,
        "1k1r4/2p4p/1pb3q1/pN6/P5Q1/2PpbBP1/1P4KP/R4R2 b - - 1 28",
        "g6g4",
        "https://lichess.org/training/SA24Y",
    ),
    (
        MotifType.PIN,
        "3r4/pp4b1/1k1p2P1/7r/4BR1p/2P3p1/PP4P1/2K4R b - - 0 30",
        "g7h6",
        "https://lichess.org/training/9ykiL",
    ),
    (
        MotifType.SKEWER,
        "2r2k2/pp3pp1/3p2p1/4p3/4P2Q/3q4/PP3P2/K5R1 w - - 0 30",
        "h4h8",
        "https://lichess.org/training/6gIhS",
    ),
    (
        MotifType.SKEWER,
        "8/5ppp/r2P4/8/8/3k1BPP/5P2/5K2 w - - 1 48",
        "f3e2",
        "https://lichess.org/training/svHit",
    ),
    (
        MotifType.SMOTHERED_MATE,
        "6rk/npq1p1bp/1p4p1/2pB1bN1/5P2/6P1/1P3B1P/7K w - - 0 29",
        "g5f7",
        "https://lichess.org/training/hs0GN",
    ),
    (
        MotifType.SMOTHERED_MATE,
        "6rk/1p4pp/p6N/3P1b2/Pq6/1P2P2P/6PK/3q4 w - - 0 36",
        "h6f7",
        "https://lichess.org/training/gDPZY",
    ),
    (
        MotifType.X_RAY,
        "4r1k1/5pp1/1b5p/4R3/1P6/B4PP1/2q1Q1KP/8 b - - 1 44",
        "c2e2",
        "https://lichess.org/training/De9KB",
    ),
    (
        MotifType.X_RAY,
        "5r1k/pp6/2p2RQp/7p/2q1N1n1/8/PPP3PP/5R1K b - - 0 22",
        "c4f1",
        "https://lichess.org/training/oCSp4",
    ),
]

# (motif, fen_before, uci) — the same near-miss fixtures already unit-tested individually
# in test_pattern_motifs.py, one per motif, reused here for the aggregate count.
NEGATIVE_CASES: list[tuple[MotifType, str, str]] = [
    (MotifType.FORK, "4k3/8/1p6/2N5/8/4p3/8/4K3 w - - 0 1", "c5d3"),
    (MotifType.PIN, "4k3/8/2n5/8/8/8/8/3B1K2 w - - 0 1", "d1c2"),
    (MotifType.SKEWER, "4k3/8/2n5/8/8/8/8/3B1K2 w - - 0 1", "d1a4"),
    (MotifType.X_RAY, "R6k/P7/8/8/8/8/6K1/7R w - - 0 1", "h1a1"),
    (MotifType.DISCOVERED_ATTACK, "4k3/8/8/8/8/8/8/B3K3 w - - 0 1", "a1e5"),
    (MotifType.DOUBLE_CHECK, "4k3/8/8/8/8/8/8/R3K3 w - - 0 1", "a1a8"),
    (MotifType.BACK_RANK_MATE, "6k1/5p1p/6p1/8/8/8/8/K2R4 w - - 0 1", "d1d8"),
    (MotifType.SMOTHERED_MATE, "7k/6pp/8/4N3/8/8/8/K7 w - - 0 1", "e5f7"),
    (MotifType.HANGING_PIECE, "k7/1b6/8/3N4/2P5/8/7R/K7 w - - 0 1", "h2h3"),
    (MotifType.REMOVING_THE_DEFENDER, "k5Q1/2n5/8/8/8/8/6K1/2R5 w - - 0 1", "c1c7"),
]


def _fires(motif: MotifType, fen_before: str, uci: str) -> bool:
    board_before = chess.Board(fen_before)
    move = chess.Move.from_uci(uci)
    assert move in board_before.legal_moves, f"{uci} illegal in {fen_before}"
    board_after = board_before.copy()
    board_after.push(move)
    return MOTIF_DETECTORS[motif](board_before, move, board_after, SETTINGS) is not None


@pytest.mark.parametrize(
    "motif,fen_before,uci,source", POSITIVE_CASES, ids=[c[3] for c in POSITIVE_CASES]
)
def test_true_positive_from_real_lichess_puzzle(
    motif: MotifType, fen_before: str, uci: str, source: str
) -> None:
    assert _fires(motif, fen_before, uci), f"missed real {motif.value} puzzle: {source}"


@pytest.mark.parametrize(
    "motif,fen_before,uci",
    NEGATIVE_CASES,
    ids=[c[0].value for c in NEGATIVE_CASES],
)
def test_true_negative_near_miss(motif: MotifType, fen_before: str, uci: str) -> None:
    assert not _fires(motif, fen_before, uci), f"false positive on {motif.value} near-miss"


def test_precision_and_recall_summary() -> None:
    """The headline Phase 6 number: aggregate precision/recall across the whole motif
    taxonomy, computed from real independently-tagged data plus the taxonomy's curated
    near-miss guards. Recorded in the Phase 6 report; thresholds here just guard against
    silent regression."""
    true_positives = sum(1 for motif, fen, uci, _ in POSITIVE_CASES if _fires(motif, fen, uci))
    false_negatives = len(POSITIVE_CASES) - true_positives
    false_positives = sum(1 for motif, fen, uci in NEGATIVE_CASES if _fires(motif, fen, uci))

    recall = true_positives / (true_positives + false_negatives)
    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives)
        else 1.0
    )

    assert recall >= 0.9, (
        f"recall {recall:.0%} below Phase 6 threshold ({true_positives}/{len(POSITIVE_CASES)})"
    )
    assert precision >= 0.9, f"precision {precision:.0%} below Phase 6 threshold"
