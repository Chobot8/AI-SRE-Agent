"""Tests for the runbook knowledge base + RAG (KAN-4, extended by KAN-21)."""

import json
from pathlib import Path

import pytest

from backend.rag import (
    Chunk,
    Citation,
    ChromaRetrievalBackend,
    DocumentMetadata,
    FaissRetrievalBackend,
    HashingEmbedder,
    KeywordVectorBackend,
    PgVectorRetrievalBackend,
    RetrievalBackend,
    RetrievalFilters,
    Retriever,
    VectorStore,
    build_index,
    citations_for,
    format_grounded_answer,
)
from backend.rag.chunking import chunk_markdown
from backend.scenarios.loader import list_packs, load_pack, to_normalized_incident

SCENARIO_SLUGS = list_packs()


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


# --- KAN-21: metadata filtering, citations, swappable backends ---------------


@pytest.mark.parametrize("slug", SCENARIO_SLUGS)
def test_scenario_pack_top_hit_matches_incident_type(slug: str) -> None:
    """Acceptance: retrieval precision on scenario packs -- for every pack (not
    one hard-coded example), the top retrieved chunk's incident_type metadata
    matches the pack's own expected scenario."""
    pack = load_pack(slug)
    incident = to_normalized_incident(pack)
    store = build_index(include_scenario_packs=True)
    retriever = Retriever(store)
    hits = retriever.retrieve_for_incident(incident, k=3)
    assert hits, slug
    assert hits[0].chunk.metadata.get("incident_type") == incident["scenario"], slug
    assert hits[0].score > 0, slug


def test_incident_type_filter_excludes_other_scenario_types() -> None:
    """Acceptance: retrieval supports metadata filters for incident type --
    filtering removes cross-type intrusions present in unfiltered results."""
    store = build_index(include_scenario_packs=True)
    retriever = Retriever(store)
    hits = retriever.retrieve(
        "latency slow p99 dependency",
        k=10,
        filters=RetrievalFilters(incident_type="high_latency"),
    )
    assert hits
    assert all(h.chunk.metadata.get("incident_type") == "high_latency" for h in hits)


def test_service_filter_excludes_other_services() -> None:
    """Acceptance: retrieval supports metadata filters for service -- results are
    scoped to that service's own chunks plus generic (service=None) runbooks."""
    store = build_index(include_scenario_packs=True)
    retriever = Retriever(store)
    hits = retriever.retrieve(
        "checkout latency slow", k=20, filters=RetrievalFilters(service="checkout-api")
    )
    assert hits
    assert all(h.chunk.metadata.get("service") in (None, "checkout-api") for h in hits)
    assert any(h.chunk.metadata.get("service") == "checkout-api" for h in hits)


def test_retrieval_filters_matches_wildcard_and_generic() -> None:
    filters = RetrievalFilters(service="checkout-api")
    assert filters.matches({"service": "checkout-api"})
    assert filters.matches({})  # generic/untagged metadata matches any filter
    assert not filters.matches({"service": "payments-api"})
    assert RetrievalFilters().is_empty
    assert not filters.is_empty


def test_document_metadata_round_trip() -> None:
    meta = DocumentMetadata(service="checkout-api", incident_type="high_latency", source="x.md")
    data = meta.to_dict()
    assert data["service"] == "checkout-api"
    restored = DocumentMetadata.from_dict(data)
    assert restored.service == "checkout-api"
    assert restored.incident_type == "high_latency"


def test_keyword_vector_backend_interface_contract() -> None:
    """Demonstrates the swappable RetrievalBackend interface against synthetic
    documents -- retrieval code does not directly depend on one hard-coded
    scenario."""
    backend: RetrievalBackend = KeywordVectorBackend()
    docs = [
        Chunk(
            id="a1",
            source="a.md",
            heading="Intro",
            text="rolling restart fixes memory leak",
            metadata={"service": "widget-api", "incident_type": "memory_leak"},
        ),
        Chunk(
            id="b1",
            source="b.md",
            heading="Intro",
            text="scale replicas to handle traffic spike",
            metadata={"service": "widget-api", "incident_type": "traffic_spike"},
        ),
    ]
    backend.index_documents(docs)
    hits = backend.search("memory leak restart", k=1)
    assert hits[0].chunk.source == "a.md"

    filtered = backend.search("fix", k=5, filters=RetrievalFilters(incident_type="traffic_spike"))
    assert all(h.chunk.metadata.get("incident_type") == "traffic_spike" for h in filtered)


def test_structured_citation_shape() -> None:
    """Acceptance: agent responses include cited retrieved chunks/evidence."""
    store = build_index()
    retriever = Retriever(store)
    hits = retriever.retrieve("connection pool exhausted lock contention", k=2)
    citations = citations_for(hits)
    assert citations
    first = citations[0]
    assert isinstance(first, Citation)
    d = first.to_dict()
    assert d["source"] == hits[0].chunk.source
    assert d["score"] == hits[0].score
    assert str(first).startswith(f"[{hits[0].chunk.source} >")


@pytest.mark.parametrize(
    "backend_cls", [ChromaRetrievalBackend, FaissRetrievalBackend, PgVectorRetrievalBackend]
)
def test_planned_backends_raise_not_implemented(backend_cls) -> None:
    """Chroma/FAISS/pgvector backends are importable and constructible now, and
    raise a clear, documented NotImplementedError until wired up -- keeping the
    retrieval backend swappable without requiring the extra dependencies today."""
    backend = backend_cls()
    assert backend.name
    with pytest.raises(NotImplementedError):
        backend.index_documents([])
    with pytest.raises(NotImplementedError):
        backend.search("query")
