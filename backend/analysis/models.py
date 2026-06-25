"""Analysis output models (KAN-5).

Stdlib dataclasses so the reasoning engine runs with no external dependencies and
its output is trivially machine-readable (``to_dict`` / ``to_json``) and
UI-displayable (``to_markdown``).
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field


def confidence_label(score: float) -> str:
    """Map a 0..1 confidence score to a label."""
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


@dataclass
class Hypothesis:
    """A ranked root-cause hypothesis."""

    cause: str
    confidence: float                       # 0..1
    evidence: list[str] = field(default_factory=list)
    recommended_checks: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)

    @property
    def confidence_label(self) -> str:
        return confidence_label(self.confidence)

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["confidence_label"] = self.confidence_label
        return d


@dataclass
class IncidentDiagnosis:
    """The full structured result of analyzing one incident."""

    incident_id: str
    service: str
    scenario: str
    status: str = "ok"                      # "ok" | "error"
    summary: str = ""
    symptoms: list[str] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    engine: str = "deterministic"           # "deterministic" | "llm"
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "service": self.service,
            "scenario": self.scenario,
            "status": self.status,
            "summary": self.summary,
            "symptoms": list(self.symptoms),
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "references": list(self.references),
            "engine": self.engine,
            "error": self.error,
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Human/UI-friendly rendering."""
        lines = [f"# Incident diagnosis — {self.incident_id} ({self.service})"]
        if self.status == "error":
            lines += ["", f"**Status:** error", f"> {self.error}"]
            return "\n".join(lines)
        lines += ["", self.summary, "", "## Symptoms"]
        lines += [f"- {s}" for s in self.symptoms] or ["- (none detected)"]
        lines += ["", "## Ranked hypotheses"]
        for i, h in enumerate(self.hypotheses, start=1):
            lines.append(
                f"\n### {i}. {h.cause}  "
                f"(confidence: {h.confidence_label}, {h.confidence:.2f})"
            )
            lines.append("Evidence:")
            lines += [f"- {e}" for e in h.evidence] or ["- (none)"]
            lines.append("Recommended checks:")
            lines += [f"- {c}" for c in h.recommended_checks] or ["- (none)"]
            if h.missing_information:
                lines.append("Missing information:")
                lines += [f"- {m}" for m in h.missing_information]
        if self.references:
            lines += ["", "## References"]
            lines += [f"- {r}" for r in self.references]
        return "\n".join(lines)
