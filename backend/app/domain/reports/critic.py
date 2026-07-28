"""Grounding critic for LLM-generated reports (Phase 9, D-023).

Structural, deterministic checks only — no second LLM call to "judge" the first. Chess
truth is never asserted by an LLM alone (`claude.md`'s RAG rules); this is the guardrail
that enforces it for reports specifically: the model's output is trusted only once it is
mechanically verified to reference nothing beyond the facts it was actually given.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.facts import Fact

# A structural heuristic, not full NLP faithfulness checking — good enough to catch the
# kid persona's one hard rule (no raw centipawn numbers) without a second model call.
_CENTIPAWN_PATTERN = re.compile(r"[+-]?\d+\s*(cp\b|centipawn)", re.IGNORECASE)


def validate_report(
    parsed: Any, facts: list[Fact], persona: Persona, settings: ReportSettings
) -> list[str]:
    """Returns a list of violations; empty means the report is grounded and safe to
    persist and show."""
    if not isinstance(parsed, dict):
        return ["response was not a JSON object"]

    findings = parsed.get("findings")
    if not isinstance(findings, list):
        return ["missing or invalid 'findings' list"]

    violations: list[str] = []
    valid_ids = {f.id for f in facts}
    for finding in findings:
        violations.extend(_validate_finding(finding, valid_ids))

    max_findings = _max_findings(persona, settings)
    if max_findings is not None and len(findings) > max_findings:
        violations.append(
            f"{len(findings)} findings exceeds the {persona.value} cap of {max_findings}"
        )

    if persona == Persona.KID and _CENTIPAWN_PATTERN.search(_full_text(parsed, findings)):
        violations.append("kid persona output mentions a centipawn value")

    return violations


def _validate_finding(finding: Any, valid_ids: set[str]) -> list[str]:
    if not isinstance(finding, dict):
        return ["a finding was not an object"]

    violations: list[str] = []
    fact_ids = finding.get("fact_ids")
    if not isinstance(fact_ids, list) or not fact_ids:
        violations.append("a finding referenced no fact_ids")
    else:
        violations.extend(
            f"referenced unknown fact id: {fid!r}" for fid in fact_ids if fid not in valid_ids
        )

    if not isinstance(finding.get("text"), str) or not finding["text"].strip():
        violations.append("a finding had no text")
    return violations


def _max_findings(persona: Persona, settings: ReportSettings) -> int | None:
    if persona == Persona.KID:
        return settings.report_kid_max_findings
    if persona == Persona.SELF_LEARNER:
        return settings.report_self_learner_max_findings
    return None


def _full_text(parsed: dict[str, Any], findings: list[Any]) -> str:
    finding_texts = [f.get("text", "") for f in findings if isinstance(f, dict)]
    recommendation_texts = [str(r) for r in parsed.get("recommendations", [])]
    return " ".join([str(parsed.get("summary", "")), *finding_texts, *recommendation_texts])


__all__ = ["validate_report"]
