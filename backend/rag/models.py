"""RAG data models (KAN-4, extended KAN-21).

Plain dataclasses (stdlib only) so the RAG layer runs without external
dependencies. The reasoning workflow (KAN-5) consumes ``RetrievedChunk`` to
ground its answers in cited operational knowledge.

KAN-21 adds structured metadata (``DocumentMetadata``), metadata filters
(``RetrievalFilters``), and a structured citation (``Citation``) alongside the
original plain-string citation -- additive only, so nothing built on the
KAN-4 shapes (``Chunk``, ``RetrievedChunk.citation``) changes behavior.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field


@dataclass
class DocumentMetadata:
    """Standard metadata fields a retrieval document can carry (KAN-21).

    Every field is optional. ``None`` means "this document doesn't specify
    that dimension" -- treated as a wildcard by :meth:`RetrievalFilters.matches`
    so generic runbooks (e.g. ``knowledge/runbooks/high_latency.md``, which has
    no single owning service) still surface under a service-scoped filter,
    while a scenario-specific snippet with an explicit, *conflicting* value is
    excluded.
    """

    service: str | None = None
    incident_type: str | None = None  # aka scenario, e.g. "pod_crash_loop"
    severity: str | None = None
    environment: str | None = None
    document_type: str = "runbook"  # "runbook" | "runbook_snippet" | "incident_history" | ...
    source: str = ""  # filename/slug the content came from
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "DocumentMetadata":
        data = dict(data or {})
        known = {f.name for f in dataclasses.fields(cls)}
        extra = dict(data.pop("extra", {}) or {})
        extra.update({k: v for k, v in data.items() if k not in known})
        kwargs = {k: v for k, v in data.items() if k in known and k != "extra"}
        return cls(extra=extra, **kwargs)


# Fields RetrievalFilters can match against, in priority/documentation order.
FILTERABLE_FIELDS = (
    "service",
    "incident_type",
    "severity",
    "environment",
    "document_type",
    "source",
)


@dataclass
class RetrievalFilters:
    """Metadata filters for :meth:`RetrievalBackend.search` (KAN-21).

    Every field is optional; an unset field imposes no constraint. Acceptance
    criterion: retrieval supports filtering by at least ``service`` and
    ``incident_type`` -- both are first-class fields here, alongside the other
    metadata dimensions from the ticket (severity, environment, document_type,
    source).
    """

    service: str | None = None
    incident_type: str | None = None
    severity: str | None = None
    environment: str | None = None
    document_type: str | None = None
    source: str | None = None

    @property
    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in FILTERABLE_FIELDS)

    def matches(self, metadata: dict | None) -> bool:
        """True if ``metadata`` satisfies every set filter field.

        A document whose metadata omits a dimension (``None``/missing) is
        treated as generic for that dimension and always matches -- only an
        explicit, differing value excludes it. This lets service-agnostic
        runbooks keep surfacing under a service filter while still letting
        scenario-specific snippets be excluded when they name a different
        service/incident type.
        """
        metadata = metadata or {}
        for name in FILTERABLE_FIELDS:
            wanted = getattr(self, name)
            if wanted is None:
                continue
            have = metadata.get(name)
            if have is None:
                continue
            if have != wanted:
                return False
        return True

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in FILTERABLE_FIELDS}


@dataclass
class Chunk:
    """A chunk of a source document ready to be embedded and indexed."""

    id: str
    source: str          # source filename, e.g. "high_latency.md"
    heading: str         # nearest section heading, e.g. "Remediation"
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Citation:
    """Structured citation for a retrieved chunk (KAN-21).

    A richer sibling of :attr:`RetrievedChunk.citation` (the plain
    ``"[source > heading]"`` string, kept unchanged for backward
    compatibility) -- this carries the metadata fields a user would want to
    see alongside "which runbook/log/evidence source was used": document
    type, service, incident type, and the similarity score.
    """

    source: str
    heading: str
    score: float
    document_type: str = "runbook"
    service: str | None = None
    incident_type: str | None = None
    severity: str | None = None
    environment: str | None = None
    text_snippet: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def __str__(self) -> str:
        return f"[{self.source} > {self.heading}] (score={self.score:.3f})"


@dataclass
class RetrievedChunk:
    """A chunk returned by retrieval, with its similarity score."""

    chunk: Chunk
    score: float

    @property
    def citation(self) -> str:
        """Human-readable citation, e.g. ``[high_latency.md > Remediation]``."""
        return f"[{self.chunk.source} > {self.chunk.heading}]"

    @property
    def structured_citation(self) -> Citation:
        """The richer :class:`Citation` view of this hit (KAN-21)."""
        meta = self.chunk.metadata or {}
        snippet = self.chunk.text[:160].strip()
        return Citation(
            source=self.chunk.source,
            heading=self.chunk.heading,
            score=self.score,
            document_type=meta.get("document_type", "runbook"),
            service=meta.get("service"),
            incident_type=meta.get("incident_type"),
            severity=meta.get("severity"),
            environment=meta.get("environment"),
            text_snippet=snippet,
        )
