"""Tone/persona-fidelity quality suite (Phase 16, `evaluation-strategy.md`).

Not part of the hermetic `tests/` suite — needs a real `OPENAI_API_KEY`. Run explicitly:

    uv run pytest evals/

`tone_fidelity_rate` is informative rather than hard-gated in this first version: unlike
`fact_invariance_rate`/`kid_safety_rate` (structural, deterministic checks that promise
zero divergence by construction), this metric is itself an LLM judgment about another
LLM's output — two stochastic layers, not one — so it is reported and trended, not used
to fail a phase, until there is a run history to judge normal variance against.
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"),
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
    pytest.mark.filterwarnings("ignore::ResourceWarning"),
]


class TestToneFidelityQuality:
    async def test_a_tone_fidelity_rate_is_recorded_per_persona(self) -> None:
        from evals.harness.tone_fidelity_eval import run

        record = await run()

        assert record["results"]["tone_fidelity_rate"] is not None
        for persona in ("self_learner", "coach", "kid"):
            assert f"{persona}.tone_fidelity_rate" in record["results"]
