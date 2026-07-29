"""Move-classifier accuracy evaluation harness (Phase 16, D-033, `project-plan.md`).

Every layer above Phase 5 — patterns, aggregates, personas, chat, training plans —
treats `MoveEvaluation.classification` as ground truth. Nothing before this module ever
validated the classification itself against an independent source; Phases 5 and 6
evaluated *around* it (legal-line validity, cross-process determinism, motif precision).

**Independence, concretely.** Ground truth here comes from a fresh Stockfish process
this harness starts itself, analysing each sampled position at
`classifier_eval_ground_truth_depth` (24 by default) — materially deeper than both the
production baseline (`engine_depth`, 12) and production's own tiered deep pass
(`engine_deep_depth`, 18, already used *inside* the system being graded). Same
`classify_move`/`compute_cpl` functions as production, deliberately: D-033 is about
where the centipawn *numbers* come from, not a second definition of what counts as a
blunder — the whole point is comparing production's classification against a better
estimate of centipawn loss, not against a different scoring rule.

Metrics:
- **detection_f1**: precision/recall/F1 for the binary "is this move notable-or-worse"
  question (inaccuracy/mistake/blunder vs. best/good), against deep-engine ground truth.
- **severity_accuracy**: exact five-way classification match rate.
- **per_class**: precision/recall/F1 for each of the five classes individually — a
  single aggregate number hides exactly the near-miss disagreements that matter most.
- **negative_control**: the same metrics recomputed against a deliberately scrambled
  ground truth. `project-plan.md`'s own requirement: "the test must be able to fail, and
  that must be demonstrated" — a metric that cannot fail proves nothing about what it
  claims to measure.

No LLM call, no `OPENAI_API_KEY` needed — a real Postgres with at least one analysed
game, and a working Stockfish binary, same requirement Phase 5's own suite has.

Usage (from `backend/`):
    uv run python -m evals.harness.classifier_accuracy_eval
"""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chess
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import EngineSettings, get_settings
from app.db.models import GameAnalysis, GameMove, MoveClassification, MoveEvaluation
from app.db.session import create_engine, create_session_factory, session_scope
from app.domain.analysis.classification import classify_move, compute_cpl
from app.integrations.engine.stockfish import StockfishEngine

RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"
HARNESS_VERSION = "phase-16-v1"
_ALL_CLASSES = list(MoveClassification)
_NOTABLE = {MoveClassification.INACCURACY, MoveClassification.MISTAKE, MoveClassification.BLUNDER}


@dataclass(frozen=True)
class SampledMove:
    game_id: str
    ply: int
    fen_before: str
    played_uci: str
    production_classification: MoveClassification


async def sample_moves(session: AsyncSession, sample_size: int) -> list[SampledMove]:
    """Up to `sample_size` real (position, production-classification) pairs, spread
    across classification buckets where the corpus has them — an all-BEST sample would
    make `severity_accuracy` look trivially high without exercising the classes where a
    classifier actually disagrees."""
    rows = (
        await session.execute(
            select(MoveEvaluation, GameAnalysis.game_id).join(
                GameAnalysis, GameAnalysis.id == MoveEvaluation.game_analysis_id
            )
        )
    ).all()
    by_class: dict[MoveClassification, list[tuple[MoveEvaluation, uuid.UUID]]] = {}
    for evaluation, game_id in rows:
        by_class.setdefault(evaluation.classification, []).append((evaluation, game_id))

    per_class_quota = max(1, sample_size // len(_ALL_CLASSES))
    chosen: list[tuple[MoveEvaluation, uuid.UUID]] = []
    for cls in _ALL_CLASSES:
        pool = by_class.get(cls, [])
        random.shuffle(pool)
        chosen.extend(pool[:per_class_quota])
    if len(chosen) < sample_size:
        remaining = [pair for pairs in by_class.values() for pair in pairs if pair not in chosen]
        random.shuffle(remaining)
        chosen.extend(remaining[: sample_size - len(chosen)])
    chosen = chosen[:sample_size]

    game_ids = {game_id for _, game_id in chosen}
    moves_by_key: dict[tuple[uuid.UUID, int], GameMove] = {}
    for move in (
        await session.execute(select(GameMove).where(GameMove.game_id.in_(game_ids)))
    ).scalars():
        moves_by_key[(move.game_id, move.ply)] = move

    sampled: list[SampledMove] = []
    for evaluation, game_id in chosen:
        game_move = moves_by_key.get((game_id, evaluation.ply))
        if game_move is None:
            continue
        sampled.append(
            SampledMove(
                game_id=str(game_id),
                ply=evaluation.ply,
                fen_before=game_move.fen_before,
                played_uci=game_move.uci,
                production_classification=evaluation.classification,
            )
        )
    return sampled


@dataclass(frozen=True)
class ScoredMove:
    sampled: SampledMove
    ground_truth_classification: MoveClassification
    ground_truth_cpl: int


async def score_against_deep_engine(
    engine: StockfishEngine, moves: list[SampledMove], *, depth: int, settings: EngineSettings
) -> list[ScoredMove]:
    scored = []
    for move in moves:
        eval_before = await engine.analyse(move.fen_before, depth=depth)
        board = chess.Board(move.fen_before)
        board.push(chess.Move.from_uci(move.played_uci))
        eval_after = await engine.analyse(board.fen(), depth=depth)
        cpl = compute_cpl(eval_before, eval_after)
        ground_truth = classify_move(
            played_uci=move.played_uci,
            best_move_uci=eval_before.best_move_uci,
            cpl=cpl,
            settings=settings,
        )
        scored.append(
            ScoredMove(sampled=move, ground_truth_classification=ground_truth, ground_truth_cpl=cpl)
        )
    return scored


def _is_notable(classification: MoveClassification) -> bool:
    return classification in _NOTABLE


def _detection_f1(scored: list[ScoredMove]) -> dict[str, float | None]:
    tp = sum(
        1
        for s in scored
        if _is_notable(s.ground_truth_classification)
        and _is_notable(s.sampled.production_classification)
    )
    fp = sum(
        1
        for s in scored
        if not _is_notable(s.ground_truth_classification)
        and _is_notable(s.sampled.production_classification)
    )
    fn = sum(
        1
        for s in scored
        if _is_notable(s.ground_truth_classification)
        and not _is_notable(s.sampled.production_classification)
    )
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else None
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def _per_class_metrics(scored: list[ScoredMove]) -> dict[str, dict[str, float | None]]:
    per_class: dict[str, dict[str, float | None]] = {}
    for cls in _ALL_CLASSES:
        tp = sum(
            1
            for s in scored
            if s.ground_truth_classification == cls and s.sampled.production_classification == cls
        )
        fp = sum(
            1
            for s in scored
            if s.ground_truth_classification != cls and s.sampled.production_classification == cls
        )
        fn = sum(
            1
            for s in scored
            if s.ground_truth_classification == cls and s.sampled.production_classification != cls
        )
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and (precision + recall) > 0
            else None
        )
        per_class[cls.value] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(1 for s in scored if s.ground_truth_classification == cls),
        }
    return per_class


def _severity_accuracy(scored: list[ScoredMove]) -> float | None:
    if not scored:
        return None
    matches = sum(
        1 for s in scored if s.ground_truth_classification == s.sampled.production_classification
    )
    return matches / len(scored)


def _score_summary(scored: list[ScoredMove]) -> dict[str, Any]:
    return {
        "detection": _detection_f1(scored),
        "severity_accuracy": _severity_accuracy(scored),
        "per_class": _per_class_metrics(scored),
        "n_scored": len(scored),
        "ground_truth_class_distribution": {
            cls.value: sum(1 for s in scored if s.ground_truth_classification == cls)
            for cls in _ALL_CLASSES
        },
    }


def _negative_control(scored: list[ScoredMove], *, seed: int = 1337) -> list[ScoredMove]:
    """The same scored moves with ground truth deliberately scrambled — a random
    permutation of the *other* moves' ground-truth labels assigned to each move, so the
    scramble cannot coincidentally reproduce the real pairing. Demonstrates the metric
    can fail: see this module's own docstring and the phase report for the recorded
    before/after numbers."""
    rng = random.Random(seed)
    shuffled_labels = [s.ground_truth_classification for s in scored]
    rng.shuffle(shuffled_labels)
    return [
        ScoredMove(
            sampled=s.sampled,
            ground_truth_classification=label,
            ground_truth_cpl=s.ground_truth_cpl,
        )
        for s, label in zip(scored, shuffled_labels, strict=True)
    ]


async def run() -> dict[str, Any]:
    settings = get_settings()
    engine_settings = get_settings().engine
    db_engine = create_engine(settings.database)
    session_factory = create_session_factory(db_engine)
    try:
        async with session_scope(session_factory) as session:
            moves = await sample_moves(session, settings.evaluation.classifier_eval_sample_size)
    finally:
        await db_engine.dispose()

    if not moves:
        record: dict[str, Any] = {
            "harness_version": HARNESS_VERSION,
            "timestamp": datetime.now(UTC).isoformat(),
            "ground_truth_depth": settings.evaluation.classifier_eval_ground_truth_depth,
            "results": {"n_scored": 0},
            "note": "No analysed games found to sample from.",
        }
        _write_run(record)
        return record

    # Generous timeout: depth 24 genuinely takes longer than production's depth 12/18
    # passes ever wait for — a fresh, independent `EngineSettings` for this eval, not a
    # mutation of the settings production analysis jobs use.
    deep_engine_settings = engine_settings.model_copy(update={"engine_timeout_s": 180})
    depth = settings.evaluation.classifier_eval_ground_truth_depth

    async with StockfishEngine(deep_engine_settings) as engine:
        scored = await score_against_deep_engine(
            engine, moves, depth=depth, settings=engine_settings
        )

    real = _score_summary(scored)
    negative = _score_summary(_negative_control(scored))

    record = {
        "harness_version": HARNESS_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
        "ground_truth_depth": depth,
        "sample_size": len(scored),
        "results": {
            "detection_f1": real["detection"]["f1"],
            "detection_precision": real["detection"]["precision"],
            "detection_recall": real["detection"]["recall"],
            "severity_accuracy": real["severity_accuracy"],
            "n_scored": real["n_scored"],
            "negative_control_detection_f1": negative["detection"]["f1"],
            "negative_control_severity_accuracy": negative["severity_accuracy"],
        },
        "per_class": real["per_class"],
        "negative_control_per_class": negative["per_class"],
        "ground_truth_class_distribution": real["ground_truth_class_distribution"],
    }
    _write_run(record)
    return record


def _write_run(record: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_classifier_accuracy.json"
    run_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    print(f"Run recorded: {run_path}")


def main() -> None:
    record = asyncio.run(run())
    print(json.dumps(record, indent=2, default=str))


if __name__ == "__main__":
    main()


__all__ = [
    "SampledMove",
    "ScoredMove",
    "run",
    "sample_moves",
    "score_against_deep_engine",
]
