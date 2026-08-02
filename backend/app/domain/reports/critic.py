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

# Per-report-kind finding vocabularies (Phase 16a's "game" format, Phase 16b's "story"
# format). `None` means that report_kind doesn't use kind-tagged findings at all
# (training plans keep their original Phase 15 shape).
_FINDING_KINDS: dict[str, frozenset[str]] = {
    "game": frozenset({"strength", "mistake"}),
    "story": frozenset({"opening", "middlegame", "endgame", "lesson"}),
    "pattern_feedback": frozenset({"repeated", "improved", "verdict"}),
}

# Phase 19: which fact kinds each pattern-feedback section is allowed to be built from.
# This is the guardrail that matters most for this report type — the failure mode is a
# model reading a "this recurred again" fact and writing "you've fixed this", which is
# both the most damaging thing it could tell a player and structurally detectable.
_PATTERN_FEEDBACK_FACT_KINDS: dict[str, frozenset[str]] = {
    "repeated": frozenset({"repeat"}),
    "improved": frozenset({"improvement"}),
    "verdict": frozenset({"verdict", "baseline"}),
}

ReportKind = Literal["game", "training", "story", "pattern_feedback"]


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

    `report_kind` (Phase 16a, D-035 addendum; extended Phase 16b) distinguishes a
    per-game findings report and a per-game full-story report (`ReportService`) from a
    profile-level training plan (`TrainingService`) — all three share this one critic
    implementation (rule 13), but the self-learner-only format rules below (a "kind"
    tag, no second person, a report-kind-specific cap) apply only to "game"/"story";
    training plans keep their original Phase 15 self-learner behaviour untouched.
    """
    if not isinstance(parsed, dict):
        return ["response was not a JSON object"]

    findings = parsed.get("findings")
    if not isinstance(findings, list):
        return ["missing or invalid 'findings' list"]

    facts_by_id = {f.id: f for f in facts}
    valid_kinds = _FINDING_KINDS.get(report_kind) if persona == Persona.SELF_LEARNER else None
    violations: list[str] = []
    for finding in findings:
        violations.extend(_validate_finding(finding, facts_by_id, valid_kinds, report_kind))

    max_findings = _max_findings(persona, settings, report_kind)
    if max_findings is not None and len(findings) > max_findings:
        violations.append(
            f"{len(findings)} findings exceeds the {persona.value} cap of {max_findings}"
        )

    # Kid's centipawn ban is a `persona-matrix.md` *safety* rule, not a house style, so
    # it stays enforced here. Self-learner and story style rules (no second person, no
    # engine numbers) deliberately do not live here: once those prompts stopped stating
    # the rules, a critic that still enforced them just burned both LLM attempts and
    # dropped every report into the deterministic fallback. Prompt and critic have to
    # agree about style; where they can't, the prompt wins and the critic keeps only
    # what is actually unsafe or structurally required (grounding, caps, `kind` tags).
    if persona == Persona.KID and _CENTIPAWN_PATTERN.search(_full_text(parsed, findings)):
        violations.append("kid persona output mentions a centipawn value")

    return violations


def _validate_finding(
    finding: Any,
    facts_by_id: dict[str, Fact],
    valid_kinds: frozenset[str] | None,
    report_kind: ReportKind,
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

    if valid_kinds is not None:
        violations.extend(
            _validate_finding_kind(finding, fact_ids, facts_by_id, valid_kinds, report_kind)
        )

    return violations


def _validate_finding_kind(
    finding: dict[str, Any],
    fact_ids: list[Any],
    facts_by_id: dict[str, Fact],
    valid_kinds: frozenset[str],
    report_kind: ReportKind,
) -> list[str]:
    """Every finding in a kind-tagged format is labelled so the frontend can group it
    under the right section header — this checks the tag is present and valid, and for
    the two formats where the tag can be cross-checked against the cited facts, that it
    is actually consistent with them, so a mislabelled finding fails the critic instead
    of silently rendering under the wrong heading.

    The "story" format's vocabulary (opening/middlegame/endgame/lesson) has no single
    fact field to cross-check against in the same way — a "lesson" finding can
    legitimately cite any kind of fact — so presence/validity is the whole check there.
    """
    kind = finding.get("kind")
    if kind not in valid_kinds:
        return [f"a self_learner finding had an invalid or missing kind: {kind!r}"]

    referenced = [facts_by_id[fid] for fid in fact_ids if fid in facts_by_id]

    if report_kind == "pattern_feedback":
        allowed = _PATTERN_FEEDBACK_FACT_KINDS[str(kind)]
        if referenced and not any(f.kind in allowed for f in referenced):
            return [f"a finding tagged {kind!r} cites no fact of kind {'/'.join(sorted(allowed))}"]
        return []

    if report_kind != "game":
        return []

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
        if report_kind == "story":
            return settings.report_story_max_findings
        if report_kind == "pattern_feedback":
            return settings.report_pattern_feedback_max_findings
        return settings.report_self_learner_max_findings
    return None


def _full_text(parsed: dict[str, Any], findings: list[Any]) -> str:
    finding_texts = [f.get("text", "") for f in findings if isinstance(f, dict)]
    recommendation_texts = [str(r) for r in parsed.get("recommendations", [])]
    return " ".join([str(parsed.get("summary", "")), *finding_texts, *recommendation_texts])


__all__ = ["ReportKind", "validate_report"]
