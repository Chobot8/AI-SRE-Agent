"""Runbook knowledge base + RAG (KAN-4).

Grounds the agent's recommendations in operational knowledge: source runbooks are
chunked, embedded, and stored in a rebuildable vector index; retrieval returns the
most relevant chunks for an incident, with citations.
"""

from backend.rag.embeddings import Embedder, HashingEmbedder, OpenAIEmbedder
from backend.rag.index import build_index, default_index_path, default_runbooks_dir
from backend.rag.models import Chunk, RetrievedChunk
from backend.rag.retriever import Retriever, format_grounded_answer, query_from_incident
from backend.rag.vector_store import VectorStore

__all__ = [
    "Chunk",
    "RetrievedChunk",
    "Embedder",
    "HashingEmbedder",
    "OpenAIEmbedder",
    "VectorStore",
    "Retriever",
    "build_index",
    "default_index_path",
    "default_runbooks_dir",
    "format_grounded_answer",
    "query_from_incident",
]
