"""Extracts structured, stably-identified facts from a game's deterministic analysis
(Phase 9, D-023).

Everything downstream — prompt construction, the grounding critic, the deterministic
fallback — operates on `Fact` objects, never on `GameAnalysis`/`MotifFinding` rows
directly. That is what keeps prompt construction and chess computation separate (rule 8
of `claude.md`): this module is the one and only place that translates deterministic
analysis into the report layer's own vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.db.models import (
    Game,
    GameAnalysis,
    GameColor,
    GameMove,
    MotifFinding,
    OpeningMatch,
    StrategicThemeFinding,
)
from app.domain.analysis.classification import display_swing_cp
from app.domain.patterns.polarity import (
    SELF_INFLICTED_MOTIFS,
    is_players_own_motif,
    is_players_own_theme,
)

FactKind = Literal[
    "summary",
    "opening",
    "move",
    "motif",
    "theme",
    "recurring_weakness",
    "knowledge_chunk",
    "phase",
    "baseline",
    "repeat",
    "improvement",
    "verdict",
]
# `recurring_weakness`/`knowledge_chunk` are produced by `training_facts.py` (Phase 15),
# `phase` by `story_facts.py` (Phase 16b), and `baseline`/`repeat`/`improvement`/`verdict`
# by `game_feedback/facts.py` (Phase 19) — not by `extract_facts` below — added here
# rather than as a second `Fact`-like type because the vocabulary (id/kind/severity/
# confidence/data) and the grounding critic (`critic.py`'s fact_id check) are already
# fully generic; each is "a new report type" (D-032), not a new fact model.
Severity = Literal["info", "notable", "critical"]

_NOTABLE_CLASSIFICATIONS = frozenset({"inaccuracy", "mistake", "blunder"})


@dataclass(frozen=True)
class Fact:
    """One addressable, stably-identified piece of ground truth about a game.

    `id` is deterministic (not a UUID) so the same fact always gets the same id across
    regenerations — that is what lets the critic check "did the model only reference
    real facts" and what lets a persona-fidelity check compare fact ids across personas.
    """

    id: str
    kind: FactKind
    severity: Severity
    ply: int | None
    confidence: float | None
    data: dict[str, Any] = field(default_factory=dict)


def extract_facts(
    *,
    game: Game,
    analysis: GameAnalysis,
    opening: OpeningMatch | None,
    motifs: list[MotifFinding],
    themes: list[StrategicThemeFinding],
    moves_by_ply: dict[int, GameMove] | None = None,
) -> list[Fact]:
    """The full candidate fact pool for a game — persona-independent. Persona-specific
    selection (caps, confidence floors) happens downstream in `selection.py`; every
    persona is generated from this exact same pool, which is what "fact-invariance"
    (`persona-matrix.md`) actually guarantees: no persona is shown a different truth,
    only a different-sized slice of the same one.

    `moves_by_ply` (Phase 16a, D-035 addendum) supplies each ply's actual SAN — optional
    and defaulted to `{}` so existing callers that only ever consumed `eval_swing_cp`/
    `classification` keep working; a fact simply has no `san` when it's omitted.
    """
    moves_by_ply = moves_by_ply or {}
    facts: list[Fact] = [_summary_fact(analysis)]

    if opening is not None:
        facts.append(_opening_fact(opening))

    focus_color = game.focus_color
    facts.extend(_move_facts(analysis, focus_color, moves_by_ply))
    facts.extend(_positive_move_facts(analysis, focus_color, moves_by_ply, motifs))
    facts.extend(_motif_facts(motifs, focus_color))
    facts.extend(_theme_facts(themes, focus_color))

    return facts


def _summary_fact(analysis: GameAnalysis) -> Fact:
    return Fact(
        id="summary",
        kind="summary",
        severity="info",
        ply=None,
        confidence=None,
        data=dict(analysis.summary),
    )


def _opening_fact(opening: OpeningMatch) -> Fact:
    return Fact(
        id="opening",
        kind="opening",
        severity="info",
        ply=opening.matched_ply,
        confidence=None,
        data={
            "eco": opening.eco,
            "opening_name": opening.opening_name,
            "matched_ply": opening.matched_ply,
        },
    )


def _side_to_move(ply: int) -> GameColor:
    """`ply` is 0-indexed (see `domain/games/parsing.py`), so an even ply is White's
    move — the same convention `GameAnalysisView.tsx`'s `moveLabel` already relies on."""
    return GameColor.WHITE if ply % 2 == 0 else GameColor.BLACK


def _move_facts(
    analysis: GameAnalysis, focus_color: GameColor | None, moves_by_ply: dict[int, GameMove]
) -> list[Fact]:
    """One fact per notable move (inaccuracy or worse) the player themselves made — only
    their own moves (by ply parity) when their side is known. When it can't be
    determined, every notable move is a candidate rather than none — same "don't
    silently hide facts on an unresolvable identity" reasoning
    `ImportService._target_profile_id` uses.
    """
    facts: list[Fact] = []
    for move in analysis.evaluations:
        if move.classification.value not in _NOTABLE_CLASSIFICATIONS:
            continue
        if focus_color is not None and _side_to_move(move.ply) != focus_color:
            continue
        severity: Severity = (
            "critical"
            if move.classification.value == "blunder" or move.is_critical_moment
            else "notable"
        )
        played = moves_by_ply.get(move.ply)
        facts.append(
            Fact(
                id=f"move-{move.ply}",
                kind="move",
                severity=severity,
                ply=move.ply,
                confidence=None,
                data={
                    "ply": move.ply,
                    "side": _side_to_move(move.ply).value,
                    "classification": move.classification.value,
                    "san": played.san if played is not None else None,
                    "eval_swing_cp": display_swing_cp(move.eval_swing_cp, move.mate_swing),
                    "mate_swing": move.mate_swing,
                    "best_move_uci": move.best_move_uci,
                    # The played move's own SAN doubles as "the better move" here — a
                    # BEST-classified move already *is* the engine's suggestion, so this
                    # is only meaningful (and only non-null) for a notable/worse move.
                    "best_move_san": move.best_move_san,
                    "is_critical_moment": move.is_critical_moment,
                },
            )
        )
    return facts


def _positive_move_facts(
    analysis: GameAnalysis,
    focus_color: GameColor | None,
    moves_by_ply: dict[int, GameMove],
    motifs: list[MotifFinding],
) -> list[Fact]:
    """One fact per strong move worth naming as a strength (Phase 16a, D-035 addendum):
    the engine's own top choice (`BEST`), at a ply where the mover also executed a real
    tactic (a motif finding recorded on their side, other than the self-inflicted
    `HANGING_PIECE`) — a fork, pin, skewer, discovered attack, or back-rank threat they
    landed, not just "the engine's suggested book move".

    Deliberately not `is_critical_moment`, despite that reading as the natural pairing:
    `is_critical_moment` fires on a large centipawn *loss* (`critical_swing_cp`), which a
    BEST move — by definition close to zero loss — essentially never has. Verified
    against real analysis data: 0 of 1928 BEST-classified rows in the dev database were
    ever also `is_critical_moment`. Tying to a landed tactic instead is what actually
    keeps "What Went Well" both meaningful (not just any book move) and non-empty.
    """
    tactics_by_ply: dict[int, MotifFinding] = {
        finding.ply: finding for finding in motifs if finding.motif not in SELF_INFLICTED_MOTIFS
    }
    facts: list[Fact] = []
    for move in analysis.evaluations:
        if move.classification.value != "best":
            continue
        if focus_color is not None and _side_to_move(move.ply) != focus_color:
            continue
        tactic = tactics_by_ply.get(move.ply)
        if tactic is None or tactic.side != _side_to_move(move.ply):
            continue
        played = moves_by_ply.get(move.ply)
        facts.append(
            Fact(
                id=f"move-{move.ply}",
                kind="move",
                severity="notable",
                ply=move.ply,
                confidence=None,
                data={
                    "ply": move.ply,
                    "side": _side_to_move(move.ply).value,
                    "classification": move.classification.value,
                    "san": played.san if played is not None else None,
                    "motif": tactic.motif.value,
                },
            )
        )
    return facts


def _motif_facts(motifs: list[MotifFinding], focus_color: GameColor | None) -> list[Fact]:
    """Every motif that is the player's own problem — see `polarity.py`. All treated as
    `"notable"`: each one already passed a real detector's confidence floor
    (`PATTERN_MIN_CONFIDENCE_TO_PERSIST`) to exist as a row at all; `confidence` itself,
    not a second severity tier, is what ranking sorts on."""
    facts: list[Fact] = []
    for finding in motifs:
        if focus_color is not None and not is_players_own_motif(finding, focus_color):
            continue
        facts.append(
            Fact(
                id=f"motif-{finding.motif.value}-{finding.ply}",
                kind="motif",
                severity="notable",
                ply=finding.ply,
                confidence=float(finding.confidence),
                data={
                    "motif": finding.motif.value,
                    "side": finding.side.value,
                    "evidence": finding.evidence,
                },
            )
        )
    return facts


def _theme_facts(themes: list[StrategicThemeFinding], focus_color: GameColor | None) -> list[Fact]:
    """Every theme that is a genuine weakness belonging to the player — see
    `polarity.py` (achievements like open-file control never become facts here)."""
    facts: list[Fact] = []
    for finding in themes:
        if focus_color is not None and not is_players_own_theme(finding, focus_color):
            continue
        facts.append(
            Fact(
                id=f"theme-{finding.theme.value}-{finding.ply}",
                kind="theme",
                severity="notable",
                ply=finding.ply,
                confidence=float(finding.confidence),
                data={
                    "theme": finding.theme.value,
                    "side": finding.side.value,
                    "evidence": finding.evidence,
                },
            )
        )
    return facts


__all__ = ["Fact", "FactKind", "Severity", "extract_facts"]
