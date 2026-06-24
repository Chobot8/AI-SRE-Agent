"""Retrieval + grounded-answer helper (KAN-4).

Retrieves the runbook chunks most relevant to an incident and formats answers
that cite the operational context they draw on. The reasoning workflow (KAN-5)
will use ``Retriever.retrieve`` and ``format_grounded_answer`` to ground its
hypotheses and recommendations.
"""

from __future__ import annotations

from backend.rag.embeddings import Embedder, HashingEmbedder
from backend.rag.models import RetrievedChunk
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


class Retriever:
    """Embeds a query and returns the top-k most similar runbook chunks."""

    def __init__(self, store: VectorStore, embedder: Embedder | None = None) -> None:
        self.store = store
        self.embedder = embedder or HashingEmbedder(dim=store.dim)

    def retrieve(self, query: str, k: int = 3) -> list[RetrievedChunk]:
        query_vector = self.embedder.embed(query)
        return self.store.search(query_vector, k=k)

    def retrieve_for_incident(self, incident: dict, k: int = 3) -> list[RetrievedChunk]:
        return self.retrieve(query_from_incident(incident), k=k)


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
