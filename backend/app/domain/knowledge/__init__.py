"""Knowledge corpus: chunking, provenance, and ingestion (Phase 7, ADR-0008).

See `ingestion.py` for the orchestrating `KnowledgeIngestionService` and
`app/db/models/knowledge.py` for why the `analysis` bucket is not part of this module —
it is generated from already-canonical game data, not curated, and lives in
`domain/retrieval/analysis_retriever.py` and `domain/knowledge/analysis_projection.py`.
"""

from app.domain.knowledge.analysis_projection import AnalysisProjectionService, ProjectedChunk
from app.domain.knowledge.chunking import Chunk, chunk_by_tokens, chunk_markdown_by_heading
from app.domain.knowledge.ingestion import IngestedDocument, KnowledgeIngestionService
from app.domain.knowledge.provenance import Provenance, ProvenanceError

__all__ = [
    "AnalysisProjectionService",
    "Chunk",
    "IngestedDocument",
    "KnowledgeIngestionService",
    "ProjectedChunk",
    "Provenance",
    "ProvenanceError",
    "chunk_by_tokens",
    "chunk_markdown_by_heading",
]
