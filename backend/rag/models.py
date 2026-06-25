"""RAG data models (KAN-4).

Plain dataclasses (stdlib only) so the RAG layer runs without external
dependencies. The reasoning workflow (KAN-5) consumes ``RetrievedChunk`` to
ground its answers in cited operational knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A chunk of a source document ready to be embedded and indexed."""

    id: str
    source: str          # source filename, e.g. "high_latency.md"
    heading: str         # nearest section heading, e.g. "Remediation"
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """A chunk returned by retrieval, with its similarity score."""

    chunk: Chunk
    score: float

    @property
    def citation(self) -> str:
        """Human-readable citation, e.g. ``[high_latency.md > Remediation]``."""
        return f"[{self.chunk.source} > {self.chunk.heading}]"
