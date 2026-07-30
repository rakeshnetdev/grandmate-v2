"""Grounding critic for LLM-generated reports (Phase 9, D-023).

Structural, deterministic checks only — no second LLM call to "judge" the first. Chess
truth is never asserted by an LLM alone (`claude.md`'s RAG rules); this is the guardrail
that enforces it for reports specifically: the model's output is trusted only once it is
mechanically verified to reference nothing beyond the facts it was actually given.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from app.core.config import ReportSettings
from app.db.models import Persona
from app.domain.reports.facts import Fact

# A structural heuristic, not full NLP faithfulness checking — good enough to catch the
# kid persona's one hard rule (no raw centipawn numbers) without a second model call.
_CENTIPAWN_PATTERN = re.compile(r"[+-]?\d+\s*(cp\b|centipawn)", re.IGNORECASE)
_SECOND_PERSON_PATTERN = re.compile(r"\byou\b|\byour\b", re.IGNORECASE)
_VALID_FINDING_KINDS = frozenset({"strength", "mistake"})

ReportKind = Literal["game", "training"]


def validate_report(
    parsed: Any,
    facts: list[Fact],
    persona: Persona,
    settings: ReportSettings,
    *,
    report_kind: ReportKind = "game",
) -> list[str]:
    """Returns a list of violations; empty means the report is grounded and safe to
    persist and show.

    `report_kind` (Phase 16a, D-035 addendum) distinguishes a per-game report
    (`ReportService`) from a profile-level training plan (`TrainingService`) — both
    share this one critic implementation (rule 13), but the self-learner-only format
    rules below (the "kind" tag, no second person, the new positive/mistake cap) are
    specific to the game-review format the owner approved; training plans keep their
    original Phase 15 self-learner behaviour untouched.
    """
    if not isinstance(parsed, dict):
        return ["response was not a JSON object"]

    findings = parsed.get("findings")
    if not isinstance(findings, list):
        return ["missing or invalid 'findings' list"]

    facts_by_id = {f.id: f for f in facts}
    is_self_learner_game = report_kind == "game" and persona == Persona.SELF_LEARNER
    violations: list[str] = []
    for finding in findings:
        violations.extend(_validate_finding(finding, facts_by_id, is_self_learner_game))

    max_findings = _max_findings(persona, settings, report_kind)
    if max_findings is not None and len(findings) > max_findings:
        violations.append(
            f"{len(findings)} findings exceeds the {persona.value} cap of {max_findings}"
        )

    full_text = _full_text(parsed, findings)
    if (persona == Persona.KID or is_self_learner_game) and _CENTIPAWN_PATTERN.search(full_text):
        violations.append(f"{persona.value} persona output mentions a centipawn value")
    if is_self_learner_game and _SECOND_PERSON_PATTERN.search(full_text):
        violations.append("self_learner game report uses second person (you/your)")

    return violations


def _validate_finding(
    finding: Any, facts_by_id: dict[str, Fact], is_self_learner_game: bool
) -> list[str]:
    if not isinstance(finding, dict):
        return ["a finding was not an object"]

    violations: list[str] = []
    fact_ids = finding.get("fact_ids")
    if not isinstance(fact_ids, list) or not fact_ids:
        violations.append("a finding referenced no fact_ids")
        fact_ids = []
    else:
        violations.extend(
            f"referenced unknown fact id: {fid!r}" for fid in fact_ids if fid not in facts_by_id
        )

    if not isinstance(finding.get("text"), str) or not finding["text"].strip():
        violations.append("a finding had no text")

    if is_self_learner_game:
        violations.extend(_validate_finding_kind(finding, fact_ids, facts_by_id))

    return violations


def _validate_finding_kind(
    finding: dict[str, Any], fact_ids: list[Any], facts_by_id: dict[str, Fact]
) -> list[str]:
    """The self-learner game format tags every finding "strength" or "mistake" so the
    frontend can group them under the right header — this checks the tag is present,
    valid, and actually consistent with the fact(s) it cites, so a mislabelled finding
    fails the critic instead of silently rendering under the wrong heading."""
    kind = finding.get("kind")
    if kind not in _VALID_FINDING_KINDS:
        return [f"a self_learner finding had an invalid or missing kind: {kind!r}"]

    referenced = [facts_by_id[fid] for fid in fact_ids if fid in facts_by_id]
    is_positive = any(f.data.get("classification") == "best" for f in referenced)
    if kind == "strength" and not is_positive:
        return ["a finding tagged 'strength' does not cite a classification=best fact"]
    if kind == "mistake" and is_positive:
        return ["a finding tagged 'mistake' cites a classification=best fact"]
    return []


def _max_findings(
    persona: Persona, settings: ReportSettings, report_kind: ReportKind
) -> int | None:
    if persona == Persona.KID:
        return settings.report_kid_max_findings
    if persona == Persona.SELF_LEARNER:
        if report_kind == "game":
            return (
                settings.report_self_learner_positive_max + settings.report_self_learner_mistake_max
            )
        return settings.report_self_learner_max_findings
    return None


def _full_text(parsed: dict[str, Any], findings: list[Any]) -> str:
    finding_texts = [f.get("text", "") for f in findings if isinstance(f, dict)]
    recommendation_texts = [str(r) for r in parsed.get("recommendations", [])]
    return " ".join([str(parsed.get("summary", "")), *finding_texts, *recommendation_texts])


__all__ = ["ReportKind", "validate_report"]
