"""Golden memory-retention dataset loading (Phase 11, `evaluation-strategy.md`).

Schema per line: `scenario_id`, `question`, `answer` (the exchange extraction judges),
`expected_kind` (`preference` | `goal` | `recurring_finding` | `null` for "should not be
remembered"), `expected_content_contains` (a lowercase substring the extracted content
should mention, `null` when `expected_kind` is `null`), and `reviewed_by` (`null` until a
human spot-checks it — the same has-provenance-vs-is-reviewed distinction every other
golden set in this project uses).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemoryRetentionScenario:
    scenario_id: str
    question: str
    answer: str
    expected_kind: str | None
    expected_content_contains: str | None
    reviewed_by: str | None

    @property
    def should_remember(self) -> bool:
        return self.expected_kind is not None


def load_memory_retention_scenarios(path: Path) -> list[MemoryRetentionScenario]:
    scenarios = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            scenarios.append(
                MemoryRetentionScenario(
                    scenario_id=row["scenario_id"],
                    question=row["question"],
                    answer=row["answer"],
                    expected_kind=row.get("expected_kind"),
                    expected_content_contains=row.get("expected_content_contains"),
                    reviewed_by=row.get("reviewed_by"),
                )
            )
    return scenarios


__all__ = ["MemoryRetentionScenario", "load_memory_retention_scenarios"]
