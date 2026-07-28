"""Persona fidelity quality suite (Phase 9, `evaluation-strategy.md`).

Not part of the hermetic `tests/` suite — this needs a real `OPENAI_API_KEY`. Run
explicitly:

    uv run pytest evals/

`fact_invariance_rate` and `kid_safety_rate` are the two guarantees this phase actually
promises (rule 9: personas may only alter framing, never truth; persona-matrix.md's kid
safety rules) — soft-gated at 1.0 here, deliberately stricter than `grounded_rate`, which
is genuinely informative-only: a real, cheap model occasionally failing a strict finding
cap and falling back is the safety net working, not a defect (see the phase report for a
concrete example observed in live testing).
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"),
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::ResourceWarning"),
]


class TestPersonaFidelityQuality:
    async def test_the_top_fact_is_never_hidden_from_any_persona(self) -> None:
        from evals.harness.persona_fidelity_eval import run

        record = await run()

        if record["reviewed_scenario_count"] == 0:
            pytest.skip(
                "Golden set has no reviewed_by entries yet — scores are informative "
                "only until a human spot-checks it (see this module's docstring)."
            )

        rate = record["results"]["fact_invariance_rate"]
        assert rate is not None
        assert rate == 1.0, f"fact_invariance_rate {rate:.3f} — a persona hid the top fact"

    async def test_the_kid_persona_never_mentions_a_centipawn_value(self) -> None:
        from evals.harness.persona_fidelity_eval import run

        record = await run()

        if record["reviewed_scenario_count"] == 0:
            pytest.skip(
                "Golden set has no reviewed_by entries yet — scores are informative "
                "only until a human spot-checks it (see this module's docstring)."
            )

        rate = record["results"]["kid_safety_rate"]
        assert rate is not None
        assert rate == 1.0, f"kid_safety_rate {rate:.3f} — the kid persona was unsafe"

    async def test_a_grounded_rate_is_recorded(self) -> None:
        """Informative only — see the module docstring for why this does not gate."""
        from evals.harness.persona_fidelity_eval import run

        record = await run()

        assert record["results"]["grounded_rate"] is not None
