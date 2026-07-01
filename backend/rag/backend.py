"""Swappable retrieval backend contract (KAN-21).

Mirrors the interface sketched in the ticket:

    class Retriever:
        def index_documents(self, documents: list[Document]) -> None: ...
        def search(self, query: str, filters: RetrievalFilters) -> list[RetrievedChunk]: ...

Named ``RetrievalBackend`` here (rather than ``Retriever``) to avoid a clash
with the existing higher-level ``backend.rag.retriever.Retriever`` (KAN-4),
which is the incident-facing facade the analysis pipeline calls; a
``RetrievalBackend`` is the swappable engine underneath it. "Document" in the
ticket's sketch is this codebase's ``Chunk`` (a chunk of a source document
ready to be embedded/indexed) — same shape, existing name kept for
continuity with KAN-4.

Every backend indexes/searches over the same ``Chunk``/``RetrievedChunk``
shapes and supports the same ``RetrievalFilters``, so callers (the analysis
pipeline, the API, tests) never depend on which backend is active — the
default, dependency-free ``KeywordVectorBackend`` can be swapped for a real
vector database without changing a single call site.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.rag.embeddings import Embedder, HashingEmbedder
from backend.rag.models import Chunk, RetrievalFilters, RetrievedChunk
from backend.rag.vector_store import VectorStore


class RetrievalBackend(ABC):
    """Contract every retrieval backend implements (KAN-21)."""

    name: str = "backend"

    @abstractmethod
    def index_documents(self, documents: list[Chunk]) -> None:
        """Add ``documents`` (chunks) to the backend's index."""

    @abstractmethod
    def search(
        self, query: str, filters: RetrievalFilters | None = None, k: int = 3
    ) -> list[RetrievedChunk]:
        """Return up to ``k`` chunks matching ``query``, restricted to ``filters``."""


class KeywordVectorBackend(RetrievalBackend):
    """Default backend: deterministic keyword/hashing embeddings + in-memory
    cosine search over a :class:`VectorStore` (KAN-4 machinery, KAN-21 filters).

    This is the "keyword-first fallback" the ticket asks to prepare for: no
    network, no API key, no external service, and fully deterministic — a
    rebuild reproduces the same vectors. See ``backend/rag/README.md`` for why
    it stays the default rather than Chroma/FAISS/pgvector for the MVP.
    """

    name = "keyword_vector"

    def __init__(self, embedder: Embedder | None = None, store: VectorStore | None = None) -> None:
        self.embedder = embedder or HashingEmbedder()
        self.store = store or VectorStore(dim=self.embedder.dim, embedder_name=self.embedder.name)

    @classmethod
    def from_store(
        cls, store: VectorStore, embedder: Embedder | None = None
    ) -> "KeywordVectorBackend":
        """Wrap an already-built :class:`VectorStore` (e.g. from ``build_index``)."""
        return cls(embedder=embedder or HashingEmbedder(dim=store.dim), store=store)

    def index_documents(self, documents: list[Chunk]) -> None:
        self.store.index_documents(documents, self.embedder)

    def search(
        self, query: str, filters: RetrievalFilters | None = None, k: int = 3
    ) -> list[RetrievedChunk]:
        query_vector = self.embedder.embed(query)
        return self.store.search(query_vector, k=k, filters=filters)


class _PlannedBackend(RetrievalBackend):
    """Base for a backend that is designed/interface-ready but not implemented
    in the MVP (KAN-21 acceptance: "prepare retrieval backend to support
    Chroma, FAISS, pgvector"). Subclasses document what real implementation
    would take; calling them raises a clear, actionable error rather than
    silently doing nothing or requiring the dependency just to import this
    module.
    """

    _requirement: str = ""

    def _not_implemented(self) -> NotImplementedError:
        return NotImplementedError(
            f"{type(self).__name__} is a planned backend, not implemented in the "
            f"MVP. {self._requirement} Use KeywordVectorBackend (the default) "
            "until it is implemented — see backend/rag/README.md."
        )

    def index_documents(self, documents: list[Chunk]) -> None:
        raise self._not_implemented()

    def search(
        self, query: str, filters: RetrievalFilters | None = None, k: int = 3
    ) -> list[RetrievedChunk]:
        raise self._not_implemented()


class ChromaRetrievalBackend(_PlannedBackend):
    """Planned Chroma-backed vector search.

    To implement: ``pip install chromadb``; wrap a persistent
    ``chromadb.PersistentClient`` collection; ``index_documents`` upserts
    ``(id, text, metadata)`` per chunk; ``search`` calls
    ``collection.query(query_texts=[query], n_results=k, where=<filters>)``
    and maps hits back onto ``RetrievedChunk``. Chroma's ``where`` clause maps
    directly onto ``RetrievalFilters`` (equality on each set field).
    """

    name = "chroma"
    _requirement = "Requires the `chromadb` package and a persistent collection."

    def __init__(self, collection_name: str = "runbooks", persist_dir: str | None = None) -> None:
        self.collection_name = collection_name
        self.persist_dir = persist_dir


class FaissRetrievalBackend(_PlannedBackend):
    """Planned FAISS-backed vector search.

    To implement: ``pip install faiss-cpu``; build an ``IndexFlatIP`` (cosine
    via normalized vectors, matching ``HashingEmbedder``'s L2-normalized
    output) or an ``IndexIVFFlat`` for larger corpora; ``index_documents``
    adds vectors and keeps a parallel ``Chunk`` list (FAISS itself is metadata
    -free); ``search`` embeds the query, queries the index, then applies
    ``RetrievalFilters`` as a post-filter over the returned ids (FAISS has no
    native metadata filtering, unlike Chroma/pgvector).
    """

    name = "faiss"
    _requirement = "Requires the `faiss-cpu` package and an on-disk/in-memory index file."

    def __init__(self, index_path: str | None = None) -> None:
        self.index_path = index_path


class PgVectorRetrievalBackend(_PlannedBackend):
    """Planned pgvector-backed vector search, using the Postgres instance
    already provisioned for the agent's persistence layer (KAN-15/16).

    To implement: enable the ``vector`` extension (see the commented-out
    ``embedding vector(1536)`` column already reserved on ``retrieved_chunks``
    in ``infra/db/schema.sql``); add an Alembic migration; add a SQLAlchemy
    model/repository; ``index_documents`` upserts rows with their embedding
    and metadata columns; ``search`` runs an ``ORDER BY embedding <=> :query``
    (cosine distance) query with a ``WHERE`` clause built from
    ``RetrievalFilters`` on the metadata columns, ``LIMIT k``.
    """

    name = "pgvector"
    _requirement = (
        "Requires the `vector` Postgres extension, a schema migration, and the "
        "`pgvector` Python package for the SQLAlchemy column type."
    )

    def __init__(self, database_url: str | None = None, table: str = "retrieved_chunks") -> None:
        self.database_url = database_url
        self.table = table
