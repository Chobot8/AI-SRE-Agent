"""Index builder (KAN-4).

Builds the vector store from the source runbooks. The store is rebuildable at any
time from ``knowledge/runbooks`` — nothing is hand-edited in the index itself.
"""

from __future__ import annotations

from pathlib import Path

from backend.rag.chunking import chunk_file
from backend.rag.embeddings import Embedder, HashingEmbedder
from backend.rag.vector_store import VectorStore


def default_runbooks_dir() -> Path:
    """Repo-root ``knowledge/runbooks`` directory."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "knowledge" / "runbooks"


def default_index_path() -> Path:
    """Repo-root ``data/rag/index.json`` (generated, git-ignored)."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "rag" / "index.json"


def build_index(
    runbooks_dir: Path | None = None,
    embedder: Embedder | None = None,
    save_to: Path | None = None,
) -> VectorStore:
    """Chunk + embed every runbook, returning a populated VectorStore.

    If ``save_to`` is given, the store is persisted there so it can be reloaded
    without re-embedding.
    """
    runbooks_dir = runbooks_dir or default_runbooks_dir()
    embedder = embedder or HashingEmbedder()
    store = VectorStore(dim=embedder.dim, embedder_name=embedder.name)

    files = sorted(runbooks_dir.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No runbooks (*.md) found in {runbooks_dir}")

    for path in files:
        for chunk in chunk_file(path):
            store.add(chunk, embedder.embed(chunk.text))

    if save_to is not None:
        store.save(save_to)
    return store
