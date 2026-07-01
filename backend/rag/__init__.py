"""Runbook knowledge base + RAG (KAN-4, extended KAN-21).

Grounds the agent's recommendations in operational knowledge: source runbooks
(plus, opt-in, scenario-pack snippets) are chunked, embedded, and stored in a
rebuildable, metadata-filterable index; retrieval returns the most relevant
chunks for an incident, with structured citations.
"""

from backend.rag.backend import (
    ChromaRetrievalBackend,
    FaissRetrievalBackend,
    KeywordVectorBackend,
    PgVectorRetrievalBackend,
    RetrievalBackend,
)
from backend.rag.embeddings import Embedder, HashingEmbedder, OpenAIEmbedder
from backend.rag.index import (
    build_index,
    default_index_path,
    default_runbooks_dir,
    default_scenarios_dir,
    scenario_pack_documents,
)
from backend.rag.models import Chunk, Citation, DocumentMetadata, RetrievalFilters, RetrievedChunk
from backend.rag.retriever import (
    Retriever,
    citations_for,
    filters_from_incident,
    format_grounded_answer,
    query_from_incident,
)
from backend.rag.vector_store import VectorStore

__all__ = [
    "Chunk",
    "Citation",
    "DocumentMetadata",
    "RetrievalFilters",
    "RetrievedChunk",
    "Embedder",
    "HashingEmbedder",
    "OpenAIEmbedder",
    "VectorStore",
    "Retriever",
    "RetrievalBackend",
    "KeywordVectorBackend",
    "ChromaRetrievalBackend",
    "FaissRetrievalBackend",
    "PgVectorRetrievalBackend",
    "build_index",
    "default_index_path",
    "default_runbooks_dir",
    "default_scenarios_dir",
    "scenario_pack_documents",
    "citations_for",
    "filters_from_incident",
    "format_grounded_answer",
    "query_from_incident",
]
