"""Knowledge corpus and retrieval storage (Phase 7, rag-architecture.md).

Two shapes, not one, because the corpus genuinely splits into two different kinds of
data (rag-architecture.md section 2):

- `knowledge_documents` / `knowledge_chunks`: the four static, curated buckets (`rules`,
  `openings`, `tactics`, `strategy`) — real documents with provenance, chunked once at
  ingestion time and re-chunked only when the source or the chunking policy changes.
- `analysis_knowledge_chunks`: the `analysis` bucket. Not a document corpus at all — a
  projection of a profile's own already-canonical game data (Phase 4-6 output) into
  retrievable text. It gets its own table, not a nullable `profile_id` on
  `knowledge_chunks`, so that profile isolation is a schema fact rather than a
  discipline: there is no code path that can query this table without a `profile_id`
  filter, because every row *requires* one. `AnalysisRetriever` (domain/retrieval) is the
  only reader, and it enforces this at the interface, not the caller (rag-architecture.md
  section 5).

`KnowledgeBucket` deliberately has four members, not five: `knowledge_documents` never
holds an `analysis` row, so "analysis" is not a valid value here. The five-bucket view
that includes `analysis` belongs to the retrieval layer's own routing, not this table.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum

# Column width for every embedding vector in this module. Must match
# `RetrievalSettings.embed_dimensions` (ADR-0008, default `text-embedding-3-small`'s
# 1536). Unlike most tunables, this genuinely cannot be a pure runtime setting: a
# pgvector column's dimension is fixed at the schema level, so changing the embedding
# model requires a new migration regardless. Settings still carries the value so the
# embedding client and this column are checked against the same number, not two
# independently-maintained ones.
EMBEDDING_DIMENSIONS = 1536


class KnowledgeBucket(enum.StrEnum):
    """The four static, curated corpus buckets. See the module docstring for why
    `analysis` is not a member here."""

    RULES = "rules"
    OPENINGS = "openings"
    TACTICS = "tactics"
    STRATEGY = "strategy"


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One curated source document, with the provenance the ingestion rules require.

    `content_hash` is what makes re-running ingestion idempotent: re-vendoring an
    unchanged source is a no-op, and a changed source replaces its chunks rather than
    accumulating stale ones alongside fresh ones (`KnowledgeIngestionService`).

    `reviewed_by` is nullable on purpose — a document enters the corpus with real
    provenance (source/licence/retrieved_at, enforced by `domain/knowledge/provenance.py`
    before ingestion ever runs) but is not yet a golden-set-grade reviewed source until a
    human has actually looked at it, per the evaluation-strategy.md distinction between
    "has provenance" and "is reviewed".
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = (UniqueConstraint("content_hash", name="uq_knowledge_documents_content_hash"),)

    bucket: Mapped[KnowledgeBucket] = mapped_column(
        pg_enum(KnowledgeBucket, "knowledge_bucket"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # e.g. "FIDE", "Wikipedia", "lichess-org/chess-openings", "GrandMate original".
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # e.g. "CC0", "CC BY-SA 4.0", "original", or an honest "licence unclear — reference/
    # educational use" rather than an invented value (rule: no provenance, no ingestion).
    licence: Mapped[str] = mapped_column(String(255), nullable=False)
    retrieved_at: Mapped[date] = mapped_column(Date, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One chunk of a `KnowledgeDocument`, embedded for dense retrieval.

    `bucket` is denormalised from the parent document (not just reachable via a join) —
    same rationale as `MotifFinding.side` in `patterns.py`: bucket-scoped retrieval is
    the primary read path, and every dense/sparse query needs to filter on it.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_knowledge_chunks_document_chunk_index"
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bucket: Mapped[KnowledgeBucket] = mapped_column(
        pg_enum(KnowledgeBucket, "knowledge_bucket"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # e.g. ECO family, motif/theme name, FIDE article number — whatever the bucket's own
    # chunker attaches (`domain/knowledge/chunking.py`); shape varies genuinely by bucket.
    chunk_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)


class AnalysisKnowledgeChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One retrievable text projection of a profile's own analysed game data — the
    `analysis` bucket. See the module docstring for why this is its own table rather
    than a nullable column on `KnowledgeChunk`.

    `profile_id` is `nullable=False` deliberately: there is no such thing as an
    unscoped row here. `AnalysisRetriever.search` takes `profile_id` as a required
    keyword argument and filters on it unconditionally — this column is what makes that
    enforceable at all.
    """

    __tablename__ = "analysis_knowledge_chunks"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # e.g. "opening", "critical_moment", "motif", "theme" — what kind of projection this
    # chunk is, set by the projector (`domain/knowledge/analysis_projection.py`).
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)


__all__ = [
    "EMBEDDING_DIMENSIONS",
    "AnalysisKnowledgeChunk",
    "KnowledgeBucket",
    "KnowledgeChunk",
    "KnowledgeDocument",
]
