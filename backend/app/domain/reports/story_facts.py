"""Facts for the full game-story report (Phase 16b): a complete opening/middlegame/
endgame narrative, not just the profile's own mistakes.

Reuses `facts.py`'s existing per-move/motif/theme extraction — that module's own
translation layer, per its docstring — called with `focus_color=None` so both sides'
moves are candidates, not just the profile's. This module adds only what the
findings-format report has no use for: phase segmentation and per-phase, per-side
aggregate stats, so the narrative can actually distinguish "your opening" from "the
opponent's middlegame."
"""

from __future__ import annotations

from collections import Counter

from app.db.models import (
    Game,
    GameAnalysis,
    GameMove,
    MotifFinding,
    OpeningMatch,
    StrategicThemeFinding,
)
from app.domain.reports.facts import (
    Fact,
    _motif_facts,
    _move_facts,
    _opening_fact,
    _positive_move_facts,
    _side_to_move,
    _summary_fact,
    _theme_facts,
)
from app.domain.reports.game_phases import GamePhases, segment_game_phases

_PHASE_ORDER = ("opening", "middlegame", "endgame")


def extract_story_facts(
    *,
    game: Game,
    analysis: GameAnalysis,
    opening: OpeningMatch | None,
    motifs: list[MotifFinding],
    themes: list[StrategicThemeFinding],
    moves_by_ply: dict[int, GameMove],
) -> list[Fact]:
    """The full candidate fact pool for the game-story report."""
    facts: list[Fact] = [_summary_fact(analysis)]
    if opening is not None:
        facts.append(_opening_fact(opening))

    # focus_color=None: both sides are candidates, unlike the findings-format report,
    # which only ever shows the profile's own moves/motifs/themes.
    facts.extend(_move_facts(analysis, None, moves_by_ply))
    facts.extend(_positive_move_facts(analysis, None, moves_by_ply, motifs))
    facts.extend(_motif_facts(motifs, None))
    facts.extend(_theme_facts(themes, None))

    ordered_moves = sorted(moves_by_ply.values(), key=lambda m: m.ply)
    phases = segment_game_phases(ordered_moves, opening)
    facts.extend(_phase_facts(analysis, phases))

    return facts


def _phase_ply_ranges(phases: GamePhases) -> dict[str, tuple[int, int]]:
    """Half-open `[start, end)` ply ranges. "middlegame"/"endgame" are omitted for a
    short, sharp game where the boundaries collapse — see `GamePhases`'s docstring."""
    ranges = {"opening": (0, phases.opening_end_ply)}
    middlegame_end = (
        phases.endgame_start_ply if phases.endgame_start_ply is not None else phases.total_plies
    )
    if middlegame_end > phases.opening_end_ply:
        ranges["middlegame"] = (phases.opening_end_ply, middlegame_end)
    if phases.endgame_start_ply is not None and phases.endgame_start_ply < phases.total_plies:
        ranges["endgame"] = (phases.endgame_start_ply, phases.total_plies)
    return ranges


def _phase_facts(analysis: GameAnalysis, phases: GamePhases) -> list[Fact]:
    """One fact per phase that actually occurred, with each side's move-quality tally
    for that ply range — the numeric backbone the narrative's Opening/Middlegame/Endgame
    sections are grounded against, so "White played accurately in the opening" is a
    checkable claim, not a vibe."""
    ranges = _phase_ply_ranges(phases)
    facts: list[Fact] = []
    for phase_name in _PHASE_ORDER:
        if phase_name not in ranges:
            continue
        start, end = ranges[phase_name]
        counts: dict[str, Counter[str]] = {"white": Counter(), "black": Counter()}
        for move in analysis.evaluations:
            if not (start <= move.ply < end):
                continue
            counts[_side_to_move(move.ply).value][move.classification.value] += 1
        facts.append(
            Fact(
                id=f"phase-{phase_name}",
                kind="phase",
                severity="info",
                ply=start,
                confidence=None,
                data={
                    "phase": phase_name,
                    "ply_start": start,
                    "ply_end": end - 1,
                    "white_counts": dict(counts["white"]),
                    "black_counts": dict(counts["black"]),
                },
            )
        )
    return facts


__all__ = ["extract_story_facts"]
