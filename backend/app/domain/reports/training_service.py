"""Training-plan generation orchestration (Phase 15, D-032).

Always generates and inserts a new row — unlike `ReportService.get_or_generate`, there is
no "fresh enough, reuse it" check. D-032's cadence decision is "generated fresh whenever
requested from current profile data," and `TrainingRecommendation`'s own docstring makes
history the mechanism recommendations use to avoid repeating themselves, so every call is
expected to produce a new row for that history to read later.

Reuses three things Phase 15 does not reinvent: `ProfileAnalyticsService` (Phase 8) for
*what* is a recurring weakness, `hybrid_search` (Phase 7) for *real* study content to
ground it, and `critic.validate_report`/the retry-then-fallback shape `ReportService`
(Phase 9) already established for turning facts into grounded, persona-framed prose.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AnalyticsSettings, LLMSettings, ReportSettings, RetrievalSettings
from app.core.devinsight import SpanKind, get_recorder
from app.db.models import KnowledgeBucket, Persona, ReportSource, TrainingRecommendation
from app.domain.analytics import ProfileAnalyticsService
from app.domain.analytics.metrics import WeaknessStats
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.reports.critic import validate_report
from app.domain.reports.facts import Fact
from app.domain.reports.queries import get_recently_recommended_themes
from app.domain.reports.training_facts import extract_training_facts
from app.domain.reports.training_fallback import build_fallback_training_plan
from app.domain.reports.training_prompts import build_training_messages
from app.domain.reports.training_selection import select_training_facts
from app.domain.retrieval import RetrievedChunk, hybrid_search
from app.integrations.llm.base import CompletionRequest, EmbeddingProvider, LLMProvider

# Same one-retry-then-fallback ceiling `ReportService` uses — a training plan still
# ungrounded after a retry falls back rather than looping or erroring.
_MAX_LLM_ATTEMPTS = 2


class TrainingService:
    def __init__(
        self,
        session: AsyncSession,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        report_settings: ReportSettings,
        llm_settings: LLMSettings,
        retrieval_settings: RetrievalSettings,
        analytics_settings: AnalyticsSettings,
    ) -> None:
        self._session = session
        self._llm = llm_provider
        self._embeddings = embedding_provider
        self._report_settings = report_settings
        self._llm_settings = llm_settings
        self._retrieval_settings = retrieval_settings
        self._analytics_settings = analytics_settings
        self._budget = LLMBudgetTracker(session, llm_settings)

    async def generate(
        self, *, profile_id: uuid.UUID, persona: Persona, window_size: int
    ) -> TrainingRecommendation:
        analytics = ProfileAnalyticsService(self._session, self._analytics_settings)
        snapshot = await analytics.compute_snapshot(profile_id, window_size)
        weaknesses = [WeaknessStats(**w) for w in snapshot.metrics.get("recurring_weaknesses", [])]

        recently_recommended = await get_recently_recommended_themes(self._session, profile_id)
        retrieved_by_weakness = await self._retrieve_for_weaknesses(weaknesses)

        facts = extract_training_facts(
            weaknesses, retrieved_by_weakness, recently_recommended=recently_recommended
        )
        selected = select_training_facts(facts, persona, self._report_settings)
        has_weaknesses = any(f.kind == "recurring_weakness" for f in selected)
        if has_weaknesses:
            content, source, model, grounded = await self._generate_content(
                selected, persona, window_size
            )
        else:
            # Nothing recurring to recommend yet — there is no chess truth for an LLM
            # call to ground, so skip straight to the fallback's "not enough signal yet"
            # message rather than spending a call and a retry on an empty FACTS list.
            content = build_fallback_training_plan(selected, persona)
            source, model, grounded = ReportSource.FALLBACK, None, True

        themes_covered = sorted(
            {f.data["name"] for f in selected if f.kind == "recurring_weakness"}
        )
        recommendation = TrainingRecommendation(
            profile_id=profile_id,
            persona=persona,
            window_size=window_size,
            snapshot_version=snapshot.snapshot_version,
            source=source,
            model=model,
            content=content,
            fact_ids_used=_collect_fact_ids(content),
            themes_covered=themes_covered,
            grounded=grounded,
        )
        self._session.add(recommendation)
        await self._session.flush()
        return recommendation

    async def _retrieve_for_weaknesses(
        self, weaknesses: list[WeaknessStats]
    ) -> dict[str, list[RetrievedChunk]]:
        """One `hybrid_search` call per weakness — motifs ground against the tactics
        bucket, themes against the strategy bucket, matching Phase 7's bucket taxonomy.
        Capped to `report_training_chunks_per_weakness` per weakness, not the full
        per-query `retrieval_top_k`, since one plan grounds several weaknesses at once."""
        retrieved: dict[str, list[RetrievedChunk]] = {}
        cap = self._report_settings.report_training_chunks_per_weakness
        for weakness in weaknesses:
            bucket = (
                KnowledgeBucket.TACTICS if weakness.kind == "motif" else KnowledgeBucket.STRATEGY
            )
            chunks = await hybrid_search(
                self._session,
                bucket=bucket,
                query=weakness.name.replace("_", " "),
                embedding_provider=self._embeddings,
                settings=self._retrieval_settings,
            )
            retrieved[weakness.name] = chunks[:cap]
        return retrieved

    async def _generate_content(
        self, facts: list[Fact], persona: Persona, window_size: int
    ) -> tuple[dict[str, Any], ReportSource, str | None, bool]:
        for attempt in range(_MAX_LLM_ATTEMPTS):
            if not await self._budget.has_budget():
                break

            messages = build_training_messages(facts, persona, window_size=window_size)
            with get_recorder().span(
                SpanKind.LLM, "training.generate", persona=persona.value, attempt=attempt
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
                SpanKind.GROUNDING, "training.critic", persona=persona.value
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

        return build_fallback_training_plan(facts, persona), ReportSource.FALLBACK, None, True


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


__all__ = ["TrainingService"]
