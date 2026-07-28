"""Reciprocal rank fusion (Phase 7, rag-architecture.md section 3): rank-based, not
score-based — dense and sparse scores are not on comparable scales."""

from __future__ import annotations

import uuid

from app.domain.retrieval.fusion import reciprocal_rank_fusion
from app.domain.retrieval.interfaces import RetrievedChunk

_A, _B, _C = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def _chunk(chunk_id: uuid.UUID, score: float, retrieved_by: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        content=f"chunk {chunk_id}",
        score=score,
        metadata={},
        retrieved_by=retrieved_by,
    )


class TestReciprocalRankFusion:
    def test_a_chunk_both_retrievers_agree_on_outranks_one_only_found_by_one(self) -> None:
        dense = [_chunk(_A, 0.9, "dense"), _chunk(_B, 0.5, "dense")]
        sparse = [_chunk(_B, 10.0, "sparse"), _chunk(_A, 1.0, "sparse")]

        fused = reciprocal_rank_fusion([dense, sparse], fusion_k=60, top_k=10)

        # A is rank 1 in dense, rank 2 in sparse; B is rank 2 in dense, rank 1 in
        # sparse — symmetric, so they should tie. Both appear; order between exact ties
        # is not asserted, but a chunk appearing in only one list must rank behind both.
        fused_ids = [chunk.chunk_id for chunk in fused]
        assert set(fused_ids) == {_A, _B}

    def test_a_chunk_only_one_retriever_found_ranks_below_a_chunk_both_found(self) -> None:
        dense = [_chunk(_A, 0.9, "dense"), _chunk(_C, 0.1, "dense")]
        sparse = [_chunk(_A, 5.0, "sparse")]

        fused = reciprocal_rank_fusion([dense, sparse], fusion_k=60, top_k=10)

        assert [chunk.chunk_id for chunk in fused] == [_A, _C]

    def test_formula_matches_the_documented_rrf_sum(self) -> None:
        dense = [_chunk(_A, 0.9, "dense")]
        sparse = [_chunk(_A, 5.0, "sparse")]

        fused = reciprocal_rank_fusion([dense, sparse], fusion_k=60, top_k=10)

        # A is rank 1 in both lists: score = 1/(60+1) + 1/(60+1)
        expected = 1.0 / 61 + 1.0 / 61
        assert fused[0].score == expected

    def test_result_is_capped_at_top_k(self) -> None:
        many = [_chunk(uuid.uuid4(), 1.0, "dense") for _ in range(5)]

        fused = reciprocal_rank_fusion([many], fusion_k=60, top_k=2)

        assert len(fused) == 2

    def test_fused_results_are_labelled_fused_not_their_source_retriever(self) -> None:
        fused = reciprocal_rank_fusion([[_chunk(_A, 1.0, "dense")]], fusion_k=60, top_k=10)

        assert fused[0].retrieved_by == "fused"

    def test_empty_input_produces_empty_output(self) -> None:
        assert reciprocal_rank_fusion([], fusion_k=60, top_k=10) == []
