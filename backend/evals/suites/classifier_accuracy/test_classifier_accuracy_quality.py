"""Move-classifier accuracy quality suite (Phase 16, D-033).

Not part of the hermetic `tests/` suite — needs a real Stockfish binary and a reachable
Postgres with analysed games to sample from. Run explicitly:

    uv run pytest evals/

Detection F1 and severity accuracy are informative here, not hard-gated: unlike
Faithfulness/Answer Accuracy (`evaluation-strategy.md`'s own hard-gated RAGAS metrics),
D-033 introduced this metric specifically to *establish* a baseline against a dev corpus
too small and unreviewed to set a defensible pass/fail line yet — see the phase report
for the actual recorded numbers and what they say about production's classifier.

What *is* asserted here is the negative control itself: `project-plan.md`'s own
requirement that "the test must be able to fail, and that must be demonstrated." A
negative-control accuracy that stayed at 1.0 would mean the metric is vacuous — this
would be the actual failure, not a score below some threshold.
"""

from __future__ import annotations

import os

import pytest

from app.core.config import EngineSettings

pytestmark = [
    pytest.mark.skipif(
        not os.path.exists(EngineSettings().stockfish_path),
        reason="Stockfish binary not found",
    ),
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::ResourceWarning"),
]


class TestClassifierAccuracyQuality:
    async def test_the_negative_control_actually_fails(self) -> None:
        from evals.harness.classifier_accuracy_eval import run

        record = await run()

        if record["results"]["n_scored"] == 0:
            pytest.skip("No analysed games in this database to sample from yet.")

        real_accuracy = record["results"]["severity_accuracy"]
        scrambled_accuracy = record["results"]["negative_control_severity_accuracy"]
        assert scrambled_accuracy is not None
        assert real_accuracy is None or scrambled_accuracy < real_accuracy, (
            "negative control did not degrade the score — the metric cannot fail, "
            "which means it proves nothing about the real run either"
        )

    async def test_detection_and_severity_scores_are_recorded(self) -> None:
        from evals.harness.classifier_accuracy_eval import run

        record = await run()

        if record["results"]["n_scored"] == 0:
            pytest.skip("No analysed games in this database to sample from yet.")

        assert record["results"]["severity_accuracy"] is not None
        assert "detection_f1" in record["results"]
