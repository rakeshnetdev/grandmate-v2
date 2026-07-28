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
    MotifFinding,
    OpeningMatch,
    StrategicThemeFinding,
)
from app.domain.patterns.polarity import is_players_own_motif, is_players_own_theme

FactKind = Literal["summary", "opening", "move", "motif", "theme"]
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
) -> list[Fact]:
    """The full candidate fact pool for a game — persona-independent. Persona-specific
    selection (caps, confidence floors) happens downstream in `selection.py`; every
    persona is generated from this exact same pool, which is what "fact-invariance"
    (`persona-matrix.md`) actually guarantees: no persona is shown a different truth,
    only a different-sized slice of the same one.
    """
    facts: list[Fact] = [_summary_fact(analysis)]

    if opening is not None:
        facts.append(_opening_fact(opening))

    focus_color = game.focus_color
    facts.extend(_move_facts(analysis, focus_color))
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


def _move_facts(analysis: GameAnalysis, focus_color: GameColor | None) -> list[Fact]:
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
        facts.append(
            Fact(
                id=f"move-{move.ply}",
                kind="move",
                severity=severity,
                ply=move.ply,
                confidence=None,
                data={
                    "ply": move.ply,
                    "classification": move.classification.value,
                    "eval_swing_cp": move.eval_swing_cp,
                    "best_move_uci": move.best_move_uci,
                    "is_critical_moment": move.is_critical_moment,
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
