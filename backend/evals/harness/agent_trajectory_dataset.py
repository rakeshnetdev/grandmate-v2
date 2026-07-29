"""Synthetic agent-trajectory dataset loading (Phase 13, D-029, `evaluation-strategy.md`).

Schema per line: `scenario_id`, `question`, `headers`/`moves`/`evaluations`/`opening` —
identical shape to `single_game_chat_dataset.py`'s golden set, reusing its
`EvaluationFixture`/`OpeningFixture`/`replay_moves` rather than redefining them (one
definition of "what a fixture ply looks like", not two) — plus two fields specific to
this dataset: `expected_needs_retrieval`/`expected_needs_analysis`, the routing a human
would consider correct for the question, scored against the multi-agent graph's actual
supervisor decision as this evaluation's tool-choice-accuracy metric.

**Synthetic, not golden** (D-029): every row's `reviewed_by` is `null`. Twelve scenarios,
three per routing category (retrieval only / analysis only / both / neither) — sized to
exercise every supervisor routing path at least a few times, deliberately smaller than
the ~30 originally proposed; see D-029 for why. A human spot-check of a sample is a
required follow-up before these scores gate anything, same rule every synthetic set in
this project follows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.harness.single_game_chat_dataset import EvaluationFixture, OpeningFixture, replay_moves

__all__ = [
    "AgentTrajectoryScenario",
    "load_agent_trajectory_scenarios",
    "replay_moves",
]


@dataclass(frozen=True)
class AgentTrajectoryScenario:
    scenario_id: str
    question: str
    headers: dict[str, str]
    moves: list[str]
    evaluations: list[EvaluationFixture]
    opening: OpeningFixture | None
    expected_needs_retrieval: bool
    expected_needs_analysis: bool
    reviewed_by: str | None

    @property
    def routing_category(self) -> str:
        """A human-readable label for grouping scores by routing category — not stored
        in the dataset itself, derived from the two expected-routing flags so the two
        never have a chance to drift out of sync with each other."""
        if self.expected_needs_retrieval and self.expected_needs_analysis:
            return "both"
        if self.expected_needs_retrieval:
            return "retrieval_only"
        if self.expected_needs_analysis:
            return "analysis_only"
        return "neither"


def load_agent_trajectory_scenarios(path: Path) -> list[AgentTrajectoryScenario]:
    scenarios = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row: dict[str, Any] = json.loads(line)
            opening = row.get("opening")
            scenarios.append(
                AgentTrajectoryScenario(
                    scenario_id=row["scenario_id"],
                    question=row["question"],
                    headers=row["headers"],
                    moves=row["moves"],
                    evaluations=[EvaluationFixture(**e) for e in row["evaluations"]],
                    opening=OpeningFixture(**opening) if opening else None,
                    expected_needs_retrieval=row["expected_needs_retrieval"],
                    expected_needs_analysis=row["expected_needs_analysis"],
                    reviewed_by=row.get("reviewed_by"),
                )
            )
    return scenarios
