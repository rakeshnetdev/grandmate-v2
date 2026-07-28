"""Retrieval quality suite (Phase 7, `evaluation-strategy.md`).

Not part of the hermetic `tests/` suite — this needs a real `OPENAI_API_KEY`, a real
Postgres connection, and an already-ingested corpus (`uv run python -m
scripts.ingest_corpus`, from `backend/`). Run explicitly:

    uv run pytest evals/

Context Precision and Context Recall are **soft** thresholds
(`evaluation-strategy.md`'s gating table) — a failure here means "investigate and
record," not "the phase is blocked," unlike the hard-gated metrics (Faithfulness,
Illegal move rate, Cross-profile leak rate) that apply from Phase 10 onward. The
assertions below still fail loudly on a real regression; soft means *the phase's own
sign-off doesn't hinge on it*, not that a drop goes unnoticed.

**Every run here also depends on the golden dataset's `reviewed_by` field being set.**
As of Phase 7's initial draft, `evals/datasets/golden/retrieval.jsonl` is entirely
self-authored and unreviewed — per the golden-vs-synthetic rule, these numbers are
informative only until a human spot-checks the set. This suite intentionally does not
silently promote itself past that; see the phase report for the review request.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from app.core.config import DatabaseSettings, get_settings

pytestmark = [
    pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"),
    # `tests/`'s hermetic suite runs with filterwarnings=["error"] (pyproject.toml) —
    # appropriate strictness for our own code, but `ragas` itself is noisy in ways that
    # have nothing to do with anything this suite is actually checking: its dependency
    # chain (langchain-community) emits a benign sunset-notice DeprecationWarning at
    # import time, and its own anonymous-telemetry module
    # (~/Library/Application Support/ragas/uuid.json) leaves a file handle that surfaces
    # as an unraisable ResourceWarning during test teardown.
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::ResourceWarning"),
    pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning"),
]


def _postgres_reachable() -> bool:
    try:
        sync_url = DatabaseSettings(database_url=get_settings().database.database_url).sync_url  # type: ignore[arg-type]
        engine = create_engine(sync_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _postgres_reachable(), reason="Postgres not reachable")
class TestRetrievalQuality:
    async def test_every_strategy_clears_the_soft_context_precision_recall_thresholds(
        self,
    ) -> None:
        from evals.harness.retrieval_eval import run

        record = await run()
        thresholds = record["thresholds"]

        if record["reviewed_query_count"] == 0:
            pytest.skip(
                "Golden set has no reviewed_by entries yet — scores are informative "
                "only until a human spot-checks it (see this module's docstring)."
            )

        for strategy, result in record["results"].items():
            precision = result["context_precision"]
            recall = result["context_recall"]
            assert precision is not None, f"{strategy}: no queries were scorable"
            assert precision >= thresholds["context_precision"], (
                f"{strategy}: context precision {precision:.3f} below soft threshold "
                f"{thresholds['context_precision']} — investigate and record, per "
                "evaluation-strategy.md"
            )
            assert recall >= thresholds["context_recall"], (
                f"{strategy}: context recall {recall:.3f} below soft threshold "
                f"{thresholds['context_recall']} — investigate and record"
            )

    async def test_hybrid_vs_baseline_comparison_is_recorded(self) -> None:
        """rag-architecture.md section 3: hybrid must beat both baselines on the
        recorded numbers, or the simpler retriever ships. This test only asserts the
        comparison was *made and recorded* — which retriever actually wins is a real
        finding to report, not something this test should force either way."""
        from evals.harness.retrieval_eval import run

        record = await run()

        assert "hybrid_beats_both_baselines" in record
        assert "recommendation" in record
