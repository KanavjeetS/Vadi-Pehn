"""
Unit tests for EmbeddingClient and RerankerClient (`services/memory-service/tests/test_embeddings.py`).
Verifies unit normalization, reproducibility, and mock reranking boosts.
"""
import math
import pytest

from memory_service.abstractions import ScoredMemoryItem
from memory_service.embeddings import MockEmbeddingClient, MockRerankerClient, NomicEmbeddingClient


@pytest.mark.asyncio
async def test_mock_embedding_client_produces_normalized_1536_dim_vectors():
    client = MockEmbeddingClient(dimensions=1536)
    vec1 = await client.embed_text("My name is Vadi and I love robotics.")
    vec2 = await client.embed_text("I need help with algebra equation.")

    assert len(vec1) == 1536
    assert len(vec2) == 1536
    assert vec1 != vec2  # Different text yields distinct vectors

    # Verify L2 norm equals 1.0 (unit circle) for accurate cosine similarity
    norm1 = math.sqrt(sum(v * v for v in vec1))
    assert math.isclose(norm1, 1.0, rel_tol=1e-5)


@pytest.mark.asyncio
async def test_mock_embedding_client_batch_processing():
    client = MockEmbeddingClient()
    texts = ["Chunk one.", "Chunk two.", "Chunk three."]
    batch = await client.embed_batch(texts)

    assert len(batch) == 3
    for vec in batch:
        assert len(vec) == 1536
        assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-5)


def test_nomic_embedding_client_normalize_vector_edge_cases():
    client = NomicEmbeddingClient(dimensions=4)
    # Zero vector
    zero_norm = client._normalize_vector([0.0, 0.0, 0.0, 0.0])
    assert zero_norm == [0.0, 0.0, 0.0, 0.0]

    # Non-zero vector
    vec = client._normalize_vector([3.0, 4.0])
    assert math.isclose(vec[0], 0.6, rel_tol=1e-5)
    assert math.isclose(vec[1], 0.8, rel_tol=1e-5)


@pytest.mark.asyncio
async def test_mock_reranker_client_boosts_exact_phrase_and_token_overlap():
    reranker = MockRerankerClient()
    candidates = [
        ScoredMemoryItem(
            memory_id="1",
            tenant_id="11111111-1111-1111-1111-111111111111",
            learner_id="22222222-2222-2222-2222-222222222222",
            content="Learner struggled with quadratic equations yesterday.",
            rrf_score=0.03,
        ),
        ScoredMemoryItem(
            memory_id="2",
            tenant_id="11111111-1111-1111-1111-111111111111",
            learner_id="22222222-2222-2222-2222-222222222222",
            content="Learner's favorite science teacher is Mr. Sharma.",
            rrf_score=0.02,
        ),
    ]

    # Query asking specifically about Mr. Sharma
    reranked = await reranker.rerank("Who is Mr. Sharma?", candidates, top_k=2)
    assert len(reranked) == 2
    # Item 2 should rank first despite lower initial RRF due to exact keyword hit
    assert reranked[0].memory_id == "2"
    assert reranked[0].rerank_score > reranked[1].rerank_score
