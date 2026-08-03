"""The multi-agent supervisor's routing plan and the coach's system message (Phase 13a).

The coach phrases chess claims only from context handed to it by upstream specialists.
These tests cover the deliberate carve-outs to that contract — the cases where empty
context is not a reason to refuse — the rule that keeps the pipeline's internals out of
user-facing text, and the `is_general_chat` signal that tells the coach which kind of
empty context it is looking at.
"""

from __future__ import annotations

from app.db.models import Persona
from app.domain.chat.multi_agent_prompts import (
    build_coach_system_message,
    parse_supervisor_plan,
)


def _coach_prompt(persona: Persona = Persona.SELF_LEARNER, *, is_general_chat: bool = False) -> str:
    return build_coach_system_message(
        persona, active_game_id=None, context=[], is_general_chat=is_general_chat
    ).content


class TestNonChessQuestionsAreAnswerableWithoutContext:
    """A question the specialists cannot gather for is still answerable.

    "How do you work?" needs no context and none can be gathered, so the coach used to
    receive an empty record and hedge: "I don't have any context available." RAGAS
    `response_relevancy` classifies a hedge as noncommittal and scores it a hard 0.000
    rather than merely low, so that single scenario decided the whole architecture
    comparison. Carved out at the prompt, the fix holds even when the supervisor
    misroutes the question to a specialist that finds nothing.
    """

    def test_questions_about_the_assistant_are_carved_out(self) -> None:
        content = _coach_prompt()

        assert "Questions about you" in content
        assert "what you can do" in content

    def test_questions_about_the_conversation_are_carved_out(self) -> None:
        content = _coach_prompt()

        assert "Questions about this conversation" in content

    def test_empty_context_is_named_as_a_wrong_reason_to_refuse(self) -> None:
        content = _coach_prompt()

        assert "empty context is not a reason to refuse" in content

    def test_the_carve_out_applies_to_every_persona(self) -> None:
        for persona in Persona:
            assert "Questions about you" in _coach_prompt(persona)


class TestChessGroundingIsUnchanged:
    """The carve-out covers non-chess questions and nothing else."""

    def test_a_chess_fact_still_requires_context(self) -> None:
        content = _coach_prompt()

        assert "You may state a chess fact only if it appears in the CONTEXT below" in content
        assert "Do not invent moves, evaluations, openings, motifs, or statistics." in content

    def test_inventing_a_citation_is_explicitly_forbidden(self) -> None:
        content = _coach_prompt()

        assert "Never invent a citation" in content


class TestUserFacingAnswersHideThePipeline:
    def test_the_coach_is_told_not_to_describe_the_architecture(self) -> None:
        """The old prompt called the coach "the phrasing specialist in a multi-agent
        pipeline", and the model duly relayed that to users as "context gathered from
        upstream specialists"."""
        content = _coach_prompt()

        assert "never mention specialists, routing" in content
        assert "phrasing specialist in a multi-agent pipeline" not in content


class TestGeneralChatRouting:
    """`is_general_chat` decides whether the specialists run at all.

    The safety property is asymmetric and worth stating plainly: a chess question wrongly
    marked general skips gathering entirely and is answered with no facts, while a general
    message wrongly marked chess only wastes a specialist call. Everything here defends
    the first direction.
    """

    def test_general_chat_suppresses_both_specialists(self) -> None:
        """Even when the model contradicts itself. Honouring both fields as written would
        send a sign-off to the retriever; the suppression makes the plan coherent before
        any caller reads it."""
        plan = parse_supervisor_plan(
            '{"is_general_chat": true, "needs_retrieval": true, "needs_analysis": true}'
        )

        assert plan["is_general_chat"] is True
        assert plan["needs_retrieval"] is False
        assert plan["needs_analysis"] is False

    def test_unparseable_output_gathers_broadly_and_is_not_general(self) -> None:
        """The failure mode has to be "gathered too much", never "answered a chess
        question from nothing"."""
        plan = parse_supervisor_plan("not json at all")

        assert plan["is_general_chat"] is False
        assert plan["needs_retrieval"] is True
        assert plan["needs_analysis"] is True

    def test_a_response_omitting_the_field_is_treated_as_a_chess_turn(self) -> None:
        """Absent means chess, not general — same asymmetry as the unparseable case."""
        plan = parse_supervisor_plan('{"needs_retrieval": true, "needs_analysis": false}')

        assert plan["is_general_chat"] is False
        assert plan["needs_retrieval"] is True


class TestTheCoachIsToldWhichEmptyContextItHas:
    """An empty context used to mean two opposite things — nothing needed gathering, or a
    specialist gathered and found nothing — which call for opposite answers. The coach had
    to re-derive that from the question; the supervisor's own judgement is passed instead.
    """

    def test_a_general_chat_turn_is_told_empty_context_is_expected(self) -> None:
        content = _coach_prompt(is_general_chat=True)

        assert "This turn is not a chess question" in content
        assert "expected rather than a failure to find material" in content

    def test_a_general_chat_turn_is_told_not_to_refuse_or_cite(self) -> None:
        content = _coach_prompt(is_general_chat=True)

        assert "Do not cite anything" in content
        assert "do not refuse" in content

    def test_a_chess_turn_is_told_an_empty_context_means_nothing_was_found(self) -> None:
        content = _coach_prompt()

        assert "If it is empty, they found nothing" in content

    def test_a_chess_turn_must_not_lead_with_what_is_missing(self) -> None:
        """Told to say plainly when it has nothing, the coach applied that to *partial*
        context too and opened with "I don't have specific information on whether your
        opening was played correctly" before answering the rest correctly. RAGAS reads the
        leading disclaimer and scores the whole answer 0.000 — `ag-opening-plan` did
        exactly that in three consecutive replicates on unchanged substance."""
        content = _coach_prompt()

        assert "Partial context is not empty context" in content
        assert "never open with a disclaimer about what you are missing" in content

    def test_a_chess_turn_keeps_the_carve_outs_as_a_misroute_safety_net(self) -> None:
        """Defence in depth: the prompt-level carve-out predates this signal and is kept,
        so a supervisor that misclassifies "how do you work?" as a chess question still
        gets an answer rather than the hedge RAGAS scores a hard 0.000."""
        content = _coach_prompt()

        assert "Questions about you" in content
        assert "empty context is not a reason to refuse" in content


class TestMultiPartQuestions:
    """A two-part question ("my biggest mistake?" plus "what is a hanging piece?") was
    answered on the analysis half only, with the retrieval half silently dropped.

    The first attempt at this rule said only "answer every part", and the coach read that
    as licence to answer the uncovered part from its own knowledge: it defined a hanging
    piece as "unprotected and can be captured without any consequence", dropping the
    corpus's "fewer defenders than attackers" case and citing nothing. Relevancy rose,
    faithfulness halved. The rule now subordinates coverage to grounding — naming a part
    as unanswerable is the correct output, an unsourced definition is not.
    """

    def test_every_part_must_be_addressed(self) -> None:
        content = _coach_prompt()

        assert "Address every part of a multi-part question" in content
        assert "Never silently drop a sub-question" in content

    def test_an_uncovered_part_may_not_be_answered_from_model_knowledge(self) -> None:
        content = _coach_prompt()

        assert "only from the context" in content
        assert "never fill one in from your own knowledge" in content
