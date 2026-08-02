"""Pattern-feedback generation orchestration (Phase 19, D-037).

Get-or-generate, the same shape `ReportService` established, with one extra staleness
condition: a stored report is also superseded when the *baseline* it was written against
has changed size. A per-game report only depends on that game's analysis, but this one
depends on the history behind it too — importing older games backfills that history, and a
report claiming "3 of your last 12" while the answer is now "3 of your last 20" is stale in
a way `analysis_version` alone cannot see.

The insufficient-baseline case never reaches the LLM at all. A player with three analyzed
games gets a plain, honest state instead of prose spun out of numbers too thin to mean
anything — and the product does not pay for a call whose output it would have to hedge.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import GameFeedbackSettings, LLMSettings, ReportSettings
from app.core.devinsight import SpanKind, get_recorder
from app.db.models import Game, GameAnalysis, GameReport, Persona, ReportSource
from app.domain.game_feedback.baseline import Baseline
from app.domain.game_feedback.comparison import GameComparison, compare_game_to_baseline
from app.domain.game_feedback.facts import extract_comparison_facts
from app.domain.game_feedback.fallback import build_fallback_feedback
from app.domain.game_feedback.prompts import build_feedback_messages
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.reports.critic import validate_report
from app.domain.reports.facts import Fact
from app.domain.reports.queries import get_latest_report
from app.integrations.llm.base import CompletionRequest, LLMProvider

# Typed as a literal, not a bare str, so it satisfies the critic's `ReportKind` without
# a cast at every call site.
REPORT_TYPE: Literal["pattern_feedback"] = "pattern_feedback"

# Same one-retry-then-fallback ceiling the other report services use.
_MAX_LLM_ATTEMPTS = 2


class PatternFeedback:
    """A comparison and, when the baseline supports one, the report written from it.

    `report` is `None` precisely when `comparison.sufficient_baseline` is False (or the
    game is unattributable) — the two travel together so a caller cannot render a verdict
    without the sample size that justifies it.
    """

    def __init__(self, comparison: GameComparison, report: GameReport | None) -> None:
        self.comparison = comparison
        self.report = report


class PatternFeedbackService:
    def __init__(
        self,
        session: AsyncSession,
        llm_provider: LLMProvider,
        feedback_settings: GameFeedbackSettings,
        report_settings: ReportSettings,
        llm_settings: LLMSettings,
    ) -> None:
        self._session = session
        self._llm = llm_provider
        self._feedback_settings = feedback_settings
        self._report_settings = report_settings
        self._llm_settings = llm_settings
        self._budget = LLMBudgetTracker(session, llm_settings)

    async def get_or_generate(
        self,
        *,
        game: Game,
        analysis: GameAnalysis,
        baseline: Baseline,
        regenerate: bool = False,
    ) -> PatternFeedback:
        """`regenerate=True` is the explicit "Regenerate" action and always spends an LLM
        call, skipping the staleness check the way `TrainingService` already does. It never
        skips the *baseline* gate below: a profile with too little history has nothing to
        regenerate from, so the button cannot be used to talk the system into a verdict it
        has already declined to make."""
        comparison = compare_game_to_baseline(
            baseline.target, baseline.prior, self._feedback_settings
        )
        if not comparison.attributable or not comparison.sufficient_baseline:
            return PatternFeedback(comparison, None)

        existing = await get_latest_report(
            self._session, game.id, Persona.SELF_LEARNER, report_type=REPORT_TYPE
        )
        if (
            not regenerate
            and existing is not None
            and existing.analysis_version == analysis.analysis_version
            and existing.content.get("baseline_games") == comparison.baseline_games
        ):
            return PatternFeedback(comparison, existing)

        facts = extract_comparison_facts(comparison)
        content, source, model = await self._generate_content(facts, game, comparison)
        # Recorded inside the stored content so the staleness check above has something
        # to compare against on the next request.
        content["baseline_games"] = comparison.baseline_games

        report = GameReport(
            game_id=game.id,
            persona=Persona.SELF_LEARNER,
            report_type=REPORT_TYPE,
            source=source,
            model=model,
            analysis_version=analysis.analysis_version,
            content=content,
            fact_ids_used=_collect_fact_ids(content),
            grounded=True,
        )
        self._session.add(report)
        await self._session.flush()
        return PatternFeedback(comparison, report)

    async def _generate_content(
        self, facts: list[Fact], game: Game, comparison: GameComparison
    ) -> tuple[dict[str, Any], ReportSource, str | None]:
        for attempt in range(_MAX_LLM_ATTEMPTS):
            if not await self._budget.has_budget():
                break

            messages = build_feedback_messages(
                facts,
                white=game.headers.get("White", "?"),
                black=game.headers.get("Black", "?"),
                result=game.headers.get("Result", "*"),
                baseline_games=comparison.baseline_games,
            )
            with get_recorder().span(
                SpanKind.LLM, "pattern_feedback.generate", attempt=attempt
            ) as span:
                response = await self._llm.complete(
                    CompletionRequest(
                        messages=messages,
                        model=self._llm_settings.llm_model,
                        response_format="json_object",
                    )
                )
                if span:
                    span.set(model=response.model)
                    span.set_tokens(response.usage.prompt_tokens, response.usage.completion_tokens)
            await self._budget.record_usage(
                response.usage.prompt_tokens, response.usage.completion_tokens
            )

            with get_recorder().span(SpanKind.GROUNDING, "pattern_feedback.critic") as span:
                parsed = _try_parse_json(response.content)
                violations = (
                    ["response was not valid JSON"]
                    if parsed is None
                    else validate_report(
                        parsed,
                        facts,
                        Persona.SELF_LEARNER,
                        self._report_settings,
                        report_kind=REPORT_TYPE,
                    )
                )
                if span:
                    span.set(violation_count=len(violations))
                if not violations and parsed is not None:
                    return parsed, ReportSource.LLM, response.model

        return build_fallback_feedback(facts), ReportSource.FALLBACK, None


def _try_parse_json(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _collect_fact_ids(content: dict[str, Any]) -> list[str]:
    ids: set[str] = set()
    for finding in content.get("findings", []):
        for fid in finding.get("fact_ids", []):
            ids.add(fid)
    return sorted(ids)


__all__ = ["REPORT_TYPE", "PatternFeedback", "PatternFeedbackService"]
