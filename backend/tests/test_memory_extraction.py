"""Memory-extraction prompt and parsing (Phase 11)."""

from __future__ import annotations

import json

from app.domain.memory.prompts import build_extraction_messages, parse_candidate_memories


class TestBuildExtractionMessages:
    def test_carries_the_question_and_answer(self) -> None:
        messages = build_extraction_messages("I want to focus on endgames", "Good plan.")

        assert messages[0].role == "system"
        assert messages[-1].role == "user"
        assert messages[-1].content is not None
        assert "I want to focus on endgames" in messages[-1].content
        assert "Good plan." in messages[-1].content


class TestParseCandidateMemories:
    def test_parses_valid_candidates(self) -> None:
        raw = json.dumps(
            {
                "memories": [
                    {"kind": "goal", "content": "Wants to improve endgames", "confidence": 0.9}
                ]
            }
        )

        candidates = parse_candidate_memories(raw)

        assert candidates == [
            {"kind": "goal", "content": "Wants to improve endgames", "confidence": 0.9}
        ]

    def test_empty_memories_list_is_valid(self) -> None:
        assert parse_candidate_memories(json.dumps({"memories": []})) == []

    def test_malformed_json_yields_no_candidates(self) -> None:
        assert parse_candidate_memories("not json") == []

    def test_unexpected_top_level_shape_yields_no_candidates(self) -> None:
        assert parse_candidate_memories(json.dumps(["goal"])) == []

    def test_missing_memories_key_yields_no_candidates(self) -> None:
        assert parse_candidate_memories(json.dumps({})) == []

    def test_an_off_taxonomy_kind_is_dropped(self) -> None:
        raw = json.dumps({"memories": [{"kind": "coach_note", "content": "x", "confidence": 0.9}]})

        assert parse_candidate_memories(raw) == []

    def test_a_blank_content_is_dropped(self) -> None:
        raw = json.dumps({"memories": [{"kind": "goal", "content": "  ", "confidence": 0.9}]})

        assert parse_candidate_memories(raw) == []

    def test_a_non_numeric_confidence_is_dropped(self) -> None:
        raw = json.dumps({"memories": [{"kind": "goal", "content": "x", "confidence": "high"}]})

        assert parse_candidate_memories(raw) == []

    def test_a_non_object_entry_is_skipped_not_fatal(self) -> None:
        raw = json.dumps({"memories": ["not an object"]})

        assert parse_candidate_memories(raw) == []

    def test_content_is_trimmed(self) -> None:
        raw = json.dumps(
            {"memories": [{"kind": "preference", "content": "  short games  ", "confidence": 0.8}]}
        )

        candidates = parse_candidate_memories(raw)

        assert candidates[0]["content"] == "short games"
