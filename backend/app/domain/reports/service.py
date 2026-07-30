"""Persona report generation orchestration (Phase 9, D-023).

Get-or-generate, not a separate "regenerate" verb: a report is (re)generated
automatically whenever none exists yet for `(game_id, persona)`, or the stored one was
built from a now-superseded `GameAnalysis` run — the same self-refreshing reasoning
`ProfileAnalyticsService` already documents for recomputing rather than serving stale
numbers from a cache.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LLMSettings, ReportSettings
from app.core.devinsight import SpanKind, get_recorder
from app.db.models import (
    Game,
    GameAnalysis,
    GameReport,
    MotifFinding,
    OpeningMatch,
    Persona,
    ReportSource,
    StrategicThemeFinding,
)
from app.domain.analysis import get_moves
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.reports.critic import validate_report
from app.domain.reports.facts import Fact, extract_facts
from app.domain.reports.fallback import build_fallback_report
from app.domain.reports.prompts import build_messages
from app.domain.reports.queries import get_latest_report
from app.domain.reports.selection import select_for_persona
from app.integrations.llm.base import CompletionRequest, LLMProvider

# One initial attempt plus one retry if the critic rejects the first — never more. A
# report still ungrounded after a retry falls back rather than looping or erroring.
_MAX_LLM_ATTEMPTS = 2


class ReportService:
    def __init__(
        self,
        session: AsyncSession,
        llm_provider: LLMProvider,
        report_settings: ReportSettings,
        llm_settings: LLMSettings,
    ) -> None:
        self._session = session
        self._llm = llm_provider
        self._report_settings = report_settings
        self._llm_settings = llm_settings
        self._budget = LLMBudgetTracker(session, llm_settings)

    async def get_or_generate(
        self,
        *,
        game: Game,
        analysis: GameAnalysis,
        opening: OpeningMatch | None,
        motifs: list[MotifFinding],
        themes: list[StrategicThemeFinding],
        persona: Persona,
    ) -> GameReport:
        existing = await get_latest_report(self._session, game.id, persona)
        if existing is not None and existing.analysis_version == analysis.analysis_version:
            return existing

        moves = await get_moves(self._session, game.id, game.profile_id)
        facts = extract_facts(
            game=game,
            analysis=analysis,
            opening=opening,
            motifs=motifs,
            themes=themes,
            moves_by_ply={move.ply: move for move in moves},
        )
        selected = select_for_persona(facts, persona, self._report_settings)
        content, source, model, grounded = await self._generate_content(selected, persona, game)

        report = GameReport(
            game_id=game.id,
            persona=persona,
            source=source,
            model=model,
            analysis_version=analysis.analysis_version,
            content=content,
            fact_ids_used=_collect_fact_ids(content),
            grounded=grounded,
        )
        self._session.add(report)
        await self._session.flush()
        return report

    async def _generate_content(
        self, facts: list[Fact], persona: Persona, game: Game
    ) -> tuple[dict[str, Any], ReportSource, str | None, bool]:
        for attempt in range(_MAX_LLM_ATTEMPTS):
            if not await self._budget.has_budget():
                break

            messages = build_messages(
                facts,
                persona,
                white=game.headers.get("White", "?"),
                black=game.headers.get("Black", "?"),
                result=game.headers.get("Result", "*"),
            )
            with get_recorder().span(
                SpanKind.LLM, "report.generate", persona=persona.value, attempt=attempt
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

            with get_recorder().span(
                SpanKind.GROUNDING, "report.critic", persona=persona.value
            ) as span:
                parsed = _try_parse_json(response.content)
                violations = (
                    ["response was not valid JSON"]
                    if parsed is None
                    else validate_report(parsed, facts, persona, self._report_settings)
                )
                if span:
                    span.set(violation_count=len(violations))
                if not violations and parsed is not None:
                    return parsed, ReportSource.LLM, response.model, True

        return build_fallback_report(facts, persona), ReportSource.FALLBACK, None, True


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


__all__ = ["ReportService"]
