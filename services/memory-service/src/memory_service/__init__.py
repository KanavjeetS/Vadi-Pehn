"""
vadi-pehn-memory-service package exposing Multi-Tenant RLS Store (`PostgresMemoryStore`),
Hybrid Retrieval (`HybridRetrievalEngine`), Contextual Summary (`ContextualRetrievalService`),
Async Write Pipeline (`AsyncMemoryWriter`), and benchmark utilities.
"""

from memory_service.abstractions import (
    ConsentCheckerClient,
    ContextualTurnSummary,
    EmbeddingClient,
    HybridRetrievalQuery,
    RerankerClient,
    ScoredMemoryItem,
)
from memory_service.benchmark import (
    BenchmarkComparisonResult,
    BenchmarkQuerySpec,
    HybridRetrievalBenchmark,
)
from memory_service.chunker import SentenceBoundaryChunker
from memory_service.context import ContextualRetrievalService
from memory_service.embeddings import (
    MockEmbeddingClient,
    MockRerankerClient,
    NomicEmbeddingClient,
)
from memory_service.retrieval import HybridRetrievalEngine
from memory_service.store import PostgresMemoryStore
from memory_service.write_pipeline import (
    AsyncMemoryWriter,
    ConsentDeniedWriteAbort,
    PostgresConsentChecker,
)

__all__ = [
    "PostgresMemoryStore",
    "EmbeddingClient",
    "RerankerClient",
    "ConsentCheckerClient",
    "ScoredMemoryItem",
    "HybridRetrievalQuery",
    "ContextualTurnSummary",
    "SentenceBoundaryChunker",
    "NomicEmbeddingClient",
    "MockEmbeddingClient",
    "MockRerankerClient",
    "HybridRetrievalEngine",
    "ContextualRetrievalService",
    "AsyncMemoryWriter",
    "ConsentDeniedWriteAbort",
    "PostgresConsentChecker",
    "HybridRetrievalBenchmark",
    "BenchmarkQuerySpec",
    "BenchmarkComparisonResult",
]
