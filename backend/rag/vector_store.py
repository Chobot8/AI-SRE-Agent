"""In-memory vector store with JSON persistence (KAN-4, extended KAN-21).

Holds chunk vectors and metadata, supports top-k cosine search (optionally
filtered on chunk metadata), and can be saved to / loaded from disk. The store
is derived data: it is always rebuildable from the source runbooks via
``backend.rag.index.build_index``.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.rag.embeddings import Embedder, cosine_similarity
from backend.rag.models import Chunk, RetrievalFilters, RetrievedChunk


class VectorStore:
    """A simple list-backed vector store."""

    def __init__(self, dim: int, embedder_name: str = "") -> None:
        self.dim = dim
        self.embedder_name = embedder_name
        self._vectors: list[list[float]] = []
        self._chunks: list[Chunk] = []

    def __len__(self) -> int:
        return len(self._chunks)

    def add(self, chunk: Chunk, vector: list[float]) -> None:
        if len(vector) != self.dim:
            raise ValueError(f"vector dim {len(vector)} != store dim {self.dim}")
        self._chunks.append(chunk)
        self._vectors.append(vector)

    def index_documents(self, chunks: list[Chunk], embedder: Embedder) -> None:
        """Embed and add every chunk (KAN-21 convenience matching the ticket's
        suggested ``index_documents`` method name)."""
        for chunk in chunks:
            self.add(chunk, embedder.embed(chunk.text))

    def search(
        self,
        query_vector: list[float],
        k: int = 3,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedChunk]:
        """Top-k cosine search, optionally restricted to chunks whose metadata
        satisfies ``filters`` (KAN-21). ``filters=None`` (the default) searches
        the whole store, unchanged from the original KAN-4 behavior.
        """
        pairs = zip(self._chunks, self._vectors)
        if filters is not None and not filters.is_empty:
            pairs = (
                (chunk, vec) for chunk, vec in pairs if filters.matches(chunk.metadata)
            )
        scored = [
            RetrievedChunk(chunk=chunk, score=cosine_similarity(query_vector, vec))
            for chunk, vec in pairs
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]

    def sources(self) -> set[str]:
        return {c.source for c in self._chunks}

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dim": self.dim,
            "embedder": self.embedder_name,
            "items": [
                {
                    "id": c.id,
                    "source": c.source,
                    "heading": c.heading,
                    "text": c.text,
                    "metadata": c.metadata,
                    "vector": v,
                }
                for c, v in zip(self._chunks, self._vectors)
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "VectorStore":
        payload = json.loads(path.read_text(encoding="utf-8"))
        store = cls(dim=payload["dim"], embedder_name=payload.get("embedder", ""))
        for item in payload["items"]:
            chunk = Chunk(
                id=item["id"],
                source=item["source"],
                heading=item["heading"],
                text=item["text"],
                metadata=item.get("metadata", {}),
            )
            store.add(chunk, item["vector"])
        return store
