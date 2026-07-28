"""Deterministic chat fallback (Phase 10)."""

from __future__ import annotations

from app.domain.chat.fallback import build_fallback_answer


def test_no_tool_results_gives_a_plain_apology_with_no_claims() -> None:
    result = build_fallback_answer([])

    assert result["citations"] == []
    assert "raw_findings" not in result
    assert isinstance(result["answer"], str) and result["answer"]


def test_tool_results_are_surfaced_verbatim_not_summarised() -> None:
    tool_results = [{"tool": "lookup_opening", "arguments": "{}", "result": {"result": None}}]

    result = build_fallback_answer(tool_results)

    assert result["citations"] == []
    assert result["raw_findings"] == tool_results
