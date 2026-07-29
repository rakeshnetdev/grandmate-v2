"""Synthetic single-game-chat dataset generation pipeline (Phase 16,
`evaluation-strategy.md`).

Implements the pipeline `evaluation-strategy.md`'s Datasets section already specifies:
sample real analysed games -> generate a question per intent category -> derive
reference facts from deterministic analysis, never from an LLM -> tag with provenance
-> freeze to `evals/datasets/synthetic/`, `reviewed_by` left `null` until a human
spot-checks a sample. "A synthetic set never silently becomes the golden set" — this
writes to `datasets/synthetic/`, never `datasets/golden/`, and nothing in the harness
reads a synthetic set as if it were reviewed.

**Deriving reference facts from `domain.reports.facts.extract_facts` matters.** It is
the exact same deterministic extraction Phase 9's reports already use — reusing it here
(rather than asking an LLM to write a reference answer) is what "derived from
deterministic analysis rather than from a model" means concretely: a reference generated
by the same class of model being evaluated would measure self-consistency, not
correctness.

Needs a reachable Postgres with at least one real, completed `GameAnalysis` to sample
from — no LLM call, no `OPENAI_API_KEY` needed, since nothing here generates prose.

Usage (from `backend/`):
    uv run python -m evals.harness.synthetic_generator
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models import (
    Game,
    GameAnalysis,
    GameMove,
    MotifFinding,
    OpeningMatch,
    StrategicThemeFinding,
)
from app.db.session import create_engine, create_session_factory, session_scope
from app.domain.reports.facts import Fact, extract_facts

GENERATOR_VERSION = "phase-16-v1"
_OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "datasets" / "synthetic" / "single_game_chat.jsonl"
)


@dataclass(frozen=True)
class SampledGame:
    game: Game
    analysis: GameAnalysis
    opening: OpeningMatch | None
    motifs: list[MotifFinding]
    themes: list[StrategicThemeFinding]
    moves: list[str]


async def sample_analyzed_games(session: AsyncSession, limit: int) -> list[SampledGame]:
    """The `limit` most recently analysed games across all profiles — a dev-time
    corpus-sampling tool, not a profile-scoped read, so no `ScopedProfileIdDep`
    equivalent applies here the way it does for a real request."""
    analysis_rows = await session.execute(
        select(GameAnalysis)
        .distinct(GameAnalysis.game_id)
        .order_by(GameAnalysis.game_id, GameAnalysis.created_at.desc())
        .options(selectinload(GameAnalysis.evaluations))
    )
    analyses = list(analysis_rows.scalars().all())
    analyses.sort(key=lambda a: a.created_at, reverse=True)
    analyses = analyses[:limit]
    if not analyses:
        return []

    game_ids = [a.game_id for a in analyses]
    games_by_id = {
        g.id: g
        for g in (await session.execute(select(Game).where(Game.id.in_(game_ids)))).scalars()
    }
    openings_by_game = {
        o.game_id: o
        for o in (
            await session.execute(select(OpeningMatch).where(OpeningMatch.game_id.in_(game_ids)))
        ).scalars()
    }
    analysis_ids = [a.id for a in analyses]
    motifs_by_analysis: dict[uuid.UUID, list[MotifFinding]] = {}
    for motif in (
        await session.execute(
            select(MotifFinding).where(MotifFinding.game_analysis_id.in_(analysis_ids))
        )
    ).scalars():
        motifs_by_analysis.setdefault(motif.game_analysis_id, []).append(motif)
    themes_by_analysis: dict[uuid.UUID, list[StrategicThemeFinding]] = {}
    for theme in (
        await session.execute(
            select(StrategicThemeFinding).where(
                StrategicThemeFinding.game_analysis_id.in_(analysis_ids)
            )
        )
    ).scalars():
        themes_by_analysis.setdefault(theme.game_analysis_id, []).append(theme)
    moves_by_game: dict[uuid.UUID, list[str]] = {}
    for move in (
        await session.execute(
            select(GameMove).where(GameMove.game_id.in_(game_ids)).order_by(GameMove.ply)
        )
    ).scalars():
        moves_by_game.setdefault(move.game_id, []).append(move.san)

    sampled = []
    for analysis in analyses:
        game = games_by_id.get(analysis.game_id)
        moves = moves_by_game.get(analysis.game_id)
        if game is None or not moves:
            continue
        sampled.append(
            SampledGame(
                game=game,
                analysis=analysis,
                opening=openings_by_game.get(analysis.game_id),
                motifs=motifs_by_analysis.get(analysis.id, []),
                themes=themes_by_analysis.get(analysis.id, []),
                moves=moves,
            )
        )
    return sampled


def _questions_for(sampled: SampledGame, facts: list[Fact]) -> dict[str, str]:
    """One question per intent (`app.domain.chat.prompts.INTENTS`), templated from this
    game's own real facts rather than a fixed generic string wherever a specific fact is
    available — e.g. `explain` names a real move/motif/theme from this exact game."""
    move_facts = [f for f in facts if f.kind == "move"]
    notable = sorted(move_facts, key=lambda f: 0 if f.severity == "critical" else 1)

    if notable:
        ply = notable[0].ply
        san = sampled.moves[ply] if ply is not None and ply < len(sampled.moves) else "that move"
        explain_q = f"Why was {san} a {notable[0].data['classification']} in this game?"
    elif sampled.opening is not None:
        explain_q = f"Why is {sampled.opening.opening_name} considered a sound opening choice?"
    else:
        explain_q = "Can you explain how the opening phase of this game went?"

    if len(move_facts) >= 2:
        a, b = notable[0], notable[-1]
        san_a = sampled.moves[a.ply] if a.ply is not None else "the first mistake"
        san_b = sampled.moves[b.ply] if b.ply is not None else "the later mistake"
        compare_q = f"Compare {san_a} to {san_b} — which mattered more?"
    else:
        compare_q = "Compare how this game might have gone with a different opening choice."

    return {
        "explain": explain_q,
        "compare": compare_q,
        "summarise": "Summarise how this game went for me.",
        "train_next": "Based on this game, what should I study or practise next?",
    }


def generate_scenarios(samples: list[SampledGame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated_at = datetime.now(UTC).isoformat()
    for sampled in samples:
        facts = extract_facts(
            game=sampled.game,
            analysis=sampled.analysis,
            opening=sampled.opening,
            motifs=sampled.motifs,
            themes=sampled.themes,
        )
        questions = _questions_for(sampled, facts)
        evaluations = [
            {
                "ply": ev.ply,
                "classification": ev.classification.value,
                "eval_cp": ev.eval_cp,
                "mate_in": ev.mate_in,
                "eval_swing_cp": ev.eval_swing_cp,
                "is_critical_moment": ev.is_critical_moment,
            }
            for ev in sorted(sampled.analysis.evaluations, key=lambda e: e.ply)
        ]
        opening_payload = (
            {
                "eco": sampled.opening.eco,
                "opening_name": sampled.opening.opening_name,
                "matched_ply": sampled.opening.matched_ply,
            }
            if sampled.opening
            else None
        )
        for intent, question in questions.items():
            rows.append(
                {
                    "scenario_id": f"synth-{sampled.game.id}-{intent}",
                    "question": question,
                    "headers": sampled.game.headers,
                    "moves": sampled.moves,
                    "evaluations": evaluations,
                    "opening": opening_payload,
                    "reference_facts": [asdict(f) for f in facts],
                    "provenance": {
                        "source_game_id": str(sampled.game.id),
                        "source_analysis_id": str(sampled.analysis.id),
                        "generated_at": generated_at,
                        "generator_version": GENERATOR_VERSION,
                    },
                    "reviewed_by": None,
                }
            )
    return rows


async def run(limit: int = 20) -> list[dict[str, Any]]:
    settings = get_settings()
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)
    try:
        async with session_scope(session_factory) as session:
            samples = await sample_analyzed_games(session, limit)
    finally:
        await engine.dispose()

    rows = generate_scenarios(samples)
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return rows


def main() -> None:
    rows = asyncio.run(run())
    print(f"Generated {len(rows)} synthetic scenarios from real analysed games.")
    print(f"Written to {_OUTPUT_PATH}")
    if not rows:
        print(
            "No analysed games found in this database — the pipeline runs correctly, "
            "there's simply nothing to sample from yet."
        )


if __name__ == "__main__":
    main()


__all__ = [
    "GENERATOR_VERSION",
    "SampledGame",
    "generate_scenarios",
    "run",
    "sample_analyzed_games",
]
