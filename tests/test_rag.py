"""Tests for the runbook knowledge base + RAG (KAN-4)."""

import json
from pathlib import Path

from backend.rag import (
    HashingEmbedder,
    Retriever,
    VectorStore,
    build_index,
    format_grounded_answer,
)
from backend.rag.chunking import chunk_markdown


def test_index_has_at_least_three_runbooks() -> None:
    """Acceptance: at least 3 runbooks are indexed."""
    store = build_index()
    assert len(store.sources()) >= 3
    assert len(store) > 0


def test_chunking_keeps_headings() -> None:
    md = "# Title\n\nIntro text.\n\n## Remediation\n\nRoll back the release."
    chunks = chunk_markdown(md, source="x.md")
    headings = {c.heading for c in chunks}
    assert "Remediation" in headings
    assert any("roll back" in c.text.lower() for c in chunks)


def test_retrieval_returns_relevant_runbook() -> None:
    """Acceptance: retrieval returns relevant chunks for a sample incident."""
    store = build_index()
    retriever = Retriever(store)
    repo_root = Path(__file__).resolve().parents[1]
    incident = json.loads(
        (repo_root / "sample-data" / "incidents" / "high_latency.json").read_text()
    )
    hits = retriever.retrieve_for_incident(incident, k=3)
    assert hits
    # The top hit should come from the matching runbook.
    assert hits[0].chunk.source == "high_latency.md"
    assert hits[0].score > 0


def test_db_saturation_incident_matches_runbook() -> None:
    store = build_index()
    retriever = Retriever(store)
    repo_root = Path(__file__).resolve().parents[1]
    incident = json.loads(
        (repo_root / "sample-data" / "incidents" / "db_saturation.json").read_text()
    )
    hits = retriever.retrieve_for_incident(incident, k=3)
    assert hits[0].chunk.source == "db_saturation.md"


def test_grounded_answer_includes_references() -> None:
    """Acceptance: agent responses include references to retrieved context."""
    store = build_index()
    retriever = Retriever(store)
    hits = retriever.retrieve("connection pool exhausted lock contention", k=2)
    answer = format_grounded_answer("Likely database saturation.", hits)
    assert "References:" in answer
    assert "[" in answer and ".md >" in answer


def test_index_rebuildable_and_deterministic(tmp_path: Path) -> None:
    """Acceptance: the vector store can be rebuilt from source documents."""
    path = tmp_path / "index.json"
    store1 = build_index(save_to=path)
    assert path.exists()
    # Reload from disk and confirm it matches a fresh rebuild.
    reloaded = VectorStore.load(path)
    store2 = build_index()
    assert len(reloaded) == len(store2) == len(store1)
    # Deterministic embeddings: a query yields the same top source either way.
    q = HashingEmbedder().embed("oomkilled crashloopbackoff memory limit")
    assert reloaded.search(q, 1)[0].chunk.source == store2.search(q, 1)[0].chunk.source
