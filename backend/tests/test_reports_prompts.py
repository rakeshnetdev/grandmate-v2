"""Unit tests for `domain/reports/prompts.py`.

Scoped to the *structural* guarantees the rest of the system depends on — the grounding
instruction every persona needs, and the `kind` tag `ReportView` groups sections by.
Deliberately not asserting on tone/style wording: that is iterated on freely, and tests
pinned to exact phrasing only broke on every edit without protecting anything real
(style is the prompt's job, not the critic's — see `critic.py`).
"""

from __future__ import annotations

import pytest

from app.db.models import Persona
from app.domain.reports.facts import Fact
from app.domain.reports.prompts import build_messages

_FACTS = [Fact(id="summary", kind="summary", severity="info", ply=None, confidence=None)]


def _system_text(persona: Persona) -> str:
    messages = build_messages(_FACTS, persona, white="A", black="B", result="1-0")
    return messages[0].content


@pytest.mark.parametrize("persona", list(Persona))
class TestEveryPersona:
    def test_states_the_json_only_output_contract(self, persona: Persona) -> None:
        text = _system_text(persona)
        assert "single JSON object" in text
        assert '"findings"' in text

    def test_requires_fact_ids_to_come_from_the_facts_list(self, persona: Persona) -> None:
        """The grounding rule the critic actually enforces — every persona must be told
        it, or the retry-then-fallback path does the work instead."""
        assert "FACTS" in _system_text(persona)


class TestKindTaggedPersonas:
    """`ReportView` groups findings into sections whenever they carry a `kind`, so a
    persona whose contract promises one must actually ask for it."""

    def test_self_learner_requires_a_kind_field(self) -> None:
        assert '"kind"' in _system_text(Persona.SELF_LEARNER)

    def test_kid_requires_a_kind_field(self) -> None:
        assert '"kind"' in _system_text(Persona.KID)

    def test_coach_does_not_use_kind_tagging(self) -> None:
        assert '"kind"' not in _system_text(Persona.COACH)


class TestUserMessage:
    def test_carries_the_game_header_and_serialised_facts(self) -> None:
        user = build_messages(_FACTS, Persona.SELF_LEARNER, white="A", black="B", result="1-0")[1]
        assert "A vs B (1-0)" in user.content
        assert '"id": "summary"' in user.content
