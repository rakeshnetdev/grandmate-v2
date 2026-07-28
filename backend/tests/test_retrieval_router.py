"""Bucket router (Phase 7): a plain keyword heuristic, not the Phase 10 agent's own
bucket-choosing tool call. See `router.py`'s module docstring for the scope boundary.
"""

from __future__ import annotations

from app.db.models import KnowledgeBucket
from app.domain.retrieval.router import select_buckets


class TestSelectBuckets:
    def test_rules_query_routes_to_rules(self) -> None:
        assert select_buckets("Is castling through check legal?") == [KnowledgeBucket.RULES]

    def test_tactics_query_routes_to_tactics(self) -> None:
        assert select_buckets("What is a knight fork?") == [KnowledgeBucket.TACTICS]

    def test_openings_query_routes_to_openings(self) -> None:
        assert select_buckets("What's the idea behind the Sicilian Defence?") == [
            KnowledgeBucket.OPENINGS
        ]

    def test_strategy_query_routes_to_strategy(self) -> None:
        assert select_buckets("How do I play against an isolated pawn?") == [
            KnowledgeBucket.STRATEGY
        ]

    def test_unclassifiable_query_falls_back_to_every_bucket(self) -> None:
        assert set(select_buckets("hello there")) == set(KnowledgeBucket)

    def test_a_query_matching_multiple_buckets_returns_all_of_them(self) -> None:
        buckets = select_buckets("What's the best plan against the Sicilian fork tactic?")

        assert KnowledgeBucket.OPENINGS in buckets
        assert KnowledgeBucket.TACTICS in buckets

    def test_matching_is_case_insensitive(self) -> None:
        assert select_buckets("WHAT IS A FORK") == [KnowledgeBucket.TACTICS]
