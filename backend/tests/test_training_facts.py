"""Unit tests for `domain/reports/training_facts.py`."""

from __future__ import annotations

import uuid

from app.domain.analytics.metrics import WeaknessStats
from app.domain.reports.training_facts import extract_training_facts
from app.domain.retrieval import RetrievedChunk


def _weakness(name: str, kind: str = "motif", occurrence_rate: float = 0.4) -> WeaknessStats:
    return WeaknessStats(
        kind=kind,  # type: ignore[arg-type]
        name=name,
        games_with_finding=4,
        occurrence_rate=occurrence_rate,
    )


def _chunk(content: str = "study this") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(), content=content, score=0.8, metadata={}, retrieved_by="fused"
    )


class TestExtractTrainingFacts:
    def test_one_weakness_fact_per_weakness(self) -> None:
        facts = extract_training_facts(
            [_weakness("fork"), _weakness("pin")], {}, recently_recommended=set()
        )
        weakness_facts = [f for f in facts if f.kind == "recurring_weakness"]
        assert {f.data["name"] for f in weakness_facts} == {"fork", "pin"}

    def test_chunks_become_knowledge_chunk_facts_tied_to_their_weakness(self) -> None:
        facts = extract_training_facts(
            [_weakness("fork")],
            {"fork": [_chunk("a fork wins material")]},
            recently_recommended=set(),
        )
        chunk_facts = [f for f in facts if f.kind == "knowledge_chunk"]
        assert len(chunk_facts) == 1
        assert chunk_facts[0].data["weakness_name"] == "fork"
        assert chunk_facts[0].data["content"] == "a fork wins material"

    def test_occurrence_rate_at_or_above_the_floor_is_critical(self) -> None:
        facts = extract_training_facts(
            [_weakness("fork", occurrence_rate=0.5)], {}, recently_recommended=set()
        )
        assert facts[0].severity == "critical"

    def test_occurrence_rate_below_the_floor_is_notable(self) -> None:
        facts = extract_training_facts(
            [_weakness("fork", occurrence_rate=0.3)], {}, recently_recommended=set()
        )
        assert facts[0].severity == "notable"

    def test_recently_recommended_is_recorded_on_the_weakness_fact_not_dropped(self) -> None:
        facts = extract_training_facts(
            [_weakness("fork"), _weakness("pin")], {}, recently_recommended={"fork"}
        )
        weakness_facts = {f.data["name"]: f for f in facts}
        assert weakness_facts["fork"].data["recently_recommended"] is True
        assert weakness_facts["pin"].data["recently_recommended"] is False
