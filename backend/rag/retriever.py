"""Retrieval + grounded-answer helper (KAN-4, extended KAN-21).

Retrieves the runbook chunks most relevant to an incident and formats answers
that cite the operational context they draw on. The reasoning workflow (KAN-5)
uses ``Retriever.retrieve``/``retrieve_for_incident`` and
``format_grounded_answer`` to ground its hypotheses and recommendations.

KAN-21 adds optional metadata filtering (``filters=``) to both retrieval
methods and a ``filters_from_incident`` helper to derive a sensible
service/incident_type filter from a normalized incident -- both are opt-in
(``filters=None`` is the default and preserves the exact KAN-4 behavior), so
existing unfiltered callers are unaffected.
"""

from __future__ import annotations

from backend.rag.embeddings import Embedder, HashingEmbedder
from backend.rag.models import Citation, RetrievalFilters, RetrievedChunk
from backend.rag.vector_store import VectorStore


def query_from_incident(incident: dict) -> str:
    """Build a retrieval query string from a normalized incident dict.

    Combines the scenario, alert summary, and notable log messages so retrieval
    keys on the actual symptoms rather than just the scenario name.
    """
    parts: list[str] = []
    if incident.get("scenario"):
        parts.append(str(incident["scenario"]).replace("_", " "))
    alert = incident.get("alert") or {}
    if alert.get("summary"):
        parts.append(alert["summary"])
    for log in (incident.get("logs") or [])[:5]:
        if log.get("message"):
            parts.append(log["message"])
    return " ".join(parts)


def filters_from_incident(incident: dict) -> RetrievalFilters:
    """Derive a service/incident_type filter from a normalized incident (KAN-21).

    Opt-in helper -- callers decide whether to pass this to ``retrieve``;
    nothing applies it automatically, so default (unfiltered) retrieval is
    unaffected.
    """
    return RetrievalFilters(
        service=incident.get("service"),
        incident_type=incident.get("scenario"),
    )


class Retriever:
    """Embeds a query and returns the top-k most similar runbook chunks."""

    def __init__(self, store: VectorStore, embedder: Embedder | None = None) -> None:
        self.store = store
        self.embedder = embedder or HashingEmbedder(dim=store.dim)

    def retrieve(
        self, query: str, k: int = 3, filters: RetrievalFilters | None = None
    ) -> list[RetrievedChunk]:
        query_vector = self.embedder.embed(query)
        return self.store.search(query_vector, k=k, filters=filters)

    def retrieve_for_incident(
        self, incident: dict, k: int = 3, filters: RetrievalFilters | None = None
    ) -> list[RetrievedChunk]:
        return self.retrieve(query_from_incident(incident), k=k, filters=filters)


def citations_for(retrieved: list[RetrievedChunk]) -> list[Citation]:
    """Map retrieved chunks onto structured :class:`Citation` objects (KAN-21)."""
    return [r.structured_citation for r in retrieved]


def format_grounded_answer(answer: str, retrieved: list[RetrievedChunk]) -> str:
    """Append a numbered References section citing the retrieved chunks.

    This guarantees agent responses include references to retrieved operational
    context (KAN-4 acceptance criterion).
    """
    lines = [answer.rstrip(), "", "References:"]
    if not retrieved:
        lines.append("- (no operational context retrieved)")
    for i, r in enumerate(retrieved, start=1):
        lines.append(f"{i}. {r.citation} (score={r.score:.3f})")
    return "\n".join(lines)
