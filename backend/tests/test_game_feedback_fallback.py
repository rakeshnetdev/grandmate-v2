"""Unit tests for the deterministic pattern-feedback fallback (Phase 19).

The fallback runs whenever the LLM path fails, so it carries the same honesty obligation
the prompt does — most of all the distinction between a weakness that is *gone* and one
that merely did not appear this game.
"""

from __future__ import annotations

from app.domain.game_feedback.comparison import (
    GameComparison,
    ImprovedWeakness,
    MetricComparison,
    RepeatedWeakness,
)
from app.domain.game_feedback.facts import extract_comparison_facts
from app.domain.game_feedback.fallback import build_fallback_feedback


def _comparison(
    *,
    repeated: list[RepeatedWeakness] | None = None,
    improved: list[ImprovedWeakness] | None = None,
    metrics: list[MetricComparison] | None = None,
) -> GameComparison:
    return GameComparison(
        baseline_games=10,
        sufficient_baseline=True,
        attributable=True,
        outcome="win",
        repeated=repeated or [],
        improved=improved or [],
        metrics=metrics or [],
        overall_band="above",
    )


def _improved(*, clear_streak: int, sustained: bool) -> ImprovedWeakness:
    return ImprovedWeakness(
        kind="motif",
        name="hanging_piece",
        baseline_games_with_finding=6,
        baseline_games=10,
        occurrence_rate=0.6,
        clear_streak=clear_streak,
        sustained=sustained,
    )


def _render(comparison: GameComparison) -> dict:
    return build_fallback_feedback(extract_comparison_facts(comparison))


class TestImprovementWording:
    def test_a_single_clean_game_is_never_called_fixed(self) -> None:
        content = _render(_comparison(improved=[_improved(clear_streak=1, sustained=False)]))
        text = next(f["text"] for f in content["findings"] if f["kind"] == "improved")
        assert "in this game" in text
        assert not any(word in text.lower() for word in ("fixed", "corrected", "improved"))

    def test_a_sustained_streak_reads_as_a_habit_kept_out(self) -> None:
        content = _render(_comparison(improved=[_improved(clear_streak=4, sustained=True)]))
        text = next(f["text"] for f in content["findings"] if f["kind"] == "improved")
        assert "kept that out of your games" in text


class TestPlainLanguage:
    """The prose sits directly under a table of the same numbers and a list of the same
    repeats with their move numbers. Restating any of it is what this section must not do
    — the reader can already see it."""

    def _all_text(self, content: dict) -> str:
        return " ".join(
            [
                content["summary"],
                *(f["text"] for f in content["findings"]),
                *content["recommendations"],
            ]
        )

    def test_no_figures_anywhere_in_the_prose(self) -> None:
        comparison = _comparison(
            repeated=[
                RepeatedWeakness(
                    kind="motif",
                    name="hanging_piece",
                    baseline_games_with_finding=6,
                    baseline_games=10,
                    occurrence_rate=0.6,
                    plies=[0, 2, 4, 6],
                )
            ],
            improved=[_improved(clear_streak=4, sustained=True)],
            metrics=[
                MetricComparison(
                    name="blunder_rate",
                    value=0.3704,
                    baseline_mean=0.13,
                    baseline_stdev=0.1,
                    z_score=-2.04,
                    band="well_below",
                )
            ],
        )
        text = self._all_text(_render(comparison))

        assert not any(char.isdigit() for char in text), text

    def test_a_repeat_still_says_it_is_a_habit(self) -> None:
        """Dropping the counts must not cost the point the counts were making."""
        repeated = RepeatedWeakness(
            kind="motif",
            name="hanging_piece",
            baseline_games_with_finding=6,
            baseline_games=10,
            occurrence_rate=0.6,
            plies=[6],
        )
        content = _render(_comparison(repeated=[repeated]))
        text = next(f["text"] for f in content["findings"] if f["kind"] == "repeated")
        assert "keep doing" in text
        # A repeat is the one thing worth acting on, so it must produce advice.
        assert content["recommendations"]

    def test_the_verdict_is_one_finding_not_one_per_metric(self) -> None:
        metrics = [
            MetricComparison(
                name=name,
                value=1.0,
                baseline_mean=2.0,
                baseline_stdev=0.5,
                z_score=-1.0,
                band="below",
            )
            for name in ("accuracy", "blunder_rate", "critical_moments")
        ]
        content = _render(_comparison(metrics=metrics))
        verdicts = [f for f in content["findings"] if f["kind"] == "verdict"]
        assert len(verdicts) == 1
        # It still cites what it rests on, even though it quotes none of it.
        assert "verdict-accuracy" in verdicts[0]["fact_ids"]


class TestGrounding:
    def test_every_finding_cites_a_real_fact(self) -> None:
        """The fallback bypasses the critic, so it has to be grounded by construction."""
        comparison = _comparison(
            repeated=[
                RepeatedWeakness(
                    kind="motif",
                    name="hanging_piece",
                    baseline_games_with_finding=6,
                    baseline_games=10,
                    occurrence_rate=0.6,
                    plies=[0],
                )
            ],
            improved=[_improved(clear_streak=3, sustained=True)],
            metrics=[
                MetricComparison(
                    name="accuracy",
                    value=78.0,
                    baseline_mean=71.0,
                    baseline_stdev=5.0,
                    z_score=1.4,
                    band="well_above",
                )
            ],
        )
        facts = extract_comparison_facts(comparison)
        known_ids = {fact.id for fact in facts}
        content = build_fallback_feedback(facts)

        assert content["findings"]
        for finding in content["findings"]:
            assert finding["fact_ids"]
            assert set(finding["fact_ids"]) <= known_ids
