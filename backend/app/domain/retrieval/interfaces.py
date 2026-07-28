"""Retrieval result types (Phase 7, rag-architecture.md).

Retrieval lives in its own domain module, behind interfaces, per rule 12 — never
inlined into a route, a prompt builder, or an agent node.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    """One retrieval result. Bucket-agnostic on purpose: a static corpus chunk and an
    `analysis`-bucket chunk both reduce to id/content/score/metadata for any caller —
    an agent building an answer, or the RAGAS harness scoring against a golden set.

    `retrieved_by` records which strategy produced this result ("dense", "sparse", or
    "fused") — not decoration: it is what lets the evaluation harness report dense vs.
    sparse vs. hybrid numbers on the same underlying result objects.
    """

    chunk_id: uuid.UUID
    content: str
    score: float
    metadata: dict[str, object]
    retrieved_by: str


__all__ = ["RetrievedChunk"]
