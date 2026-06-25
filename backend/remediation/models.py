"""Remediation models (KAN-6).

Structured, advisory-only remediation recommendations. The MVP never executes
actions — these objects describe *what a human could do*, with the evidence, risk,
rollback note, and approval requirement needed to decide safely.

Stdlib dataclasses: machine-readable (to_dict/to_json) and UI-displayable
(to_markdown).
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from enum import Enum


class ActionCategory(str, Enum):
    """Allowed remediation categories (the only actions the agent may suggest)."""

    INVESTIGATE = "investigate"
    ROLLBACK = "rollback"
    SCALE = "scale"
    RESTART = "restart"
    TUNE_CONFIG = "tune_config"
    PAGE_OWNER = "page_owner"
    OPEN_TICKET = "open_ticket"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


@dataclass
class Recommendation:
    """A single suggested action. Advisory only — never auto-executed."""

    action: ActionCategory
    title: str
    rationale: str
    evidence: list[str] = field(default_factory=list)
    risk: RiskLevel = RiskLevel.low
    rollback_note: str = "N/A — non-mutating action."
    approval_required: bool = False
    production_impacting: bool = False
    # Fixed marker: there is no execution path in the MVP.
    execution: str = "manual_only"

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["action"] = self.action.value
        d["risk"] = self.risk.value
        return d


@dataclass
class RemediationPlan:
    """Ordered set of recommendations for one incident."""

    incident_id: str
    scenario: str
    service: str
    recommendations: list[Recommendation] = field(default_factory=list)
    # Stated on every plan so the advisory-only contract is explicit.
    note: str = (
        "Advisory only. The agent does not execute any remediation automatically "
        "in the MVP. Actions flagged approval-required must be reviewed and "
        "performed by a human."
    )

    @property
    def approval_required_actions(self) -> list[Recommendation]:
        return [r for r in self.recommendations if r.approval_required]

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "scenario": self.scenario,
            "service": self.service,
            "auto_execution": False,
            "note": self.note,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        lines = [
            f"# Remediation plan — {self.incident_id} ({self.service})",
            "",
            f"_{self.note}_",
            "",
        ]
        for i, r in enumerate(self.recommendations, start=1):
            flag = "  ⚠️ approval-required" if r.approval_required else ""
            lines.append(f"## {i}. [{r.action.value}] {r.title}{flag}")
            lines.append(f"- **Risk:** {r.risk.value}"
                         + (" (production-impacting)" if r.production_impacting else ""))
            lines.append(f"- **Rationale:** {r.rationale}")
            if r.evidence:
                lines.append("- **Evidence:**")
                lines += [f"    - {e}" for e in r.evidence]
            lines.append(f"- **Rollback:** {r.rollback_note}")
            lines.append("")
        return "\n".join(lines)
