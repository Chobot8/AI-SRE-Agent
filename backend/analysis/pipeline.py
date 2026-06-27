"""Incident analysis pipeline (KAN-5).

Turns a normalized incident into a structured, ranked diagnosis:

    summarize alert -> collect context (metrics/logs + runbook retrieval)
    -> identify symptoms -> rank likely causes -> propose next checks

Deterministic by default; an optional LLMClient can propose hypotheses, with
deterministic fallback when its output is incomplete. Always returns a valid
IncidentDiagnosis — failure cases carry a diagnostic error, never an empty result.
"""

from __future__ import annotations

from backend.analysis.detectors import detect, symptoms_from_signals
from backend.analysis.knowledge import CAUSE_TEMPLATES, GENERIC_TEMPLATES, CauseTemplate
from backend.analysis.llm import LLMClient, validate_llm_hypotheses
from backend.analysis.models import Hypothesis, IncidentDiagnosis

# Optional: runbook retrieval for grounded references (KAN-4). Imported lazily so
# analysis works even if the RAG layer is unavailable.
try:
    from backend.rag import Retriever, build_index, query_from_incident
    _RAG_AVAILABLE = True
except Exception:  # pragma: no cover - defensive
    _RAG_AVAILABLE = False


def _score(template: CauseTemplate, signals: set[str]) -> tuple[float, list[str]]:
    """Confidence score + matched signal tokens for a cause template."""
    if not template.signals:
        return template.base_confidence, []
    matched = [s for s in template.signals if s in signals]
    if not matched:
        return 0.0, []
    coverage = len(matched) / len(template.signals)
    return round(template.base_confidence * coverage, 3), matched


class IncidentAnalyzer:
    """Produces a ranked, evidence-backed diagnosis for an incident."""

    def __init__(self, retriever=None, llm: LLMClient | None = None) -> None:
        self._retriever = retriever
        self._llm = llm

    # --- context: runbook references -------------------------------------
    def _references(self, incident: dict) -> list[str]:
        if not _RAG_AVAILABLE:
            return []
        try:
            retriever = self._retriever or Retriever(build_index())
            hits = retriever.retrieve(query_from_incident(incident), k=3)
            return [h.citation for h in hits]
        except Exception:  # pragma: no cover - references are best-effort
            return []

    # --- deterministic ranking -------------------------------------------
    def _deterministic_hypotheses(
        self, scenario: str, signals: set[str], evidence: dict[str, str]
    ) -> list[Hypothesis]:
        templates = CAUSE_TEMPLATES.get(scenario, [])
        ranked: list[Hypothesis] = []
        for tpl in templates:
            score, matched = _score(tpl, signals)
            if score <= 0:
                continue
            ev = [evidence.get(tok, tok) for tok in matched]
            ranked.append(
                Hypothesis(
                    cause=tpl.cause,
                    confidence=score,
                    evidence=ev,
                    recommended_checks=list(tpl.recommended_checks),
                    missing_information=list(tpl.missing_information),
                )
            )
        ranked.sort(key=lambda h: h.confidence, reverse=True)
        if not ranked:
            tpl = GENERIC_TEMPLATES[0]
            ranked = [
                Hypothesis(
                    cause=tpl.cause,
                    confidence=tpl.base_confidence,
                    evidence=(
                        symptoms_from_signals(signals, evidence)
                        or ["No dominant signal detected"]
                    ),
                    recommended_checks=list(tpl.recommended_checks),
                    missing_information=list(tpl.missing_information),
                )
            ]
        return ranked

    # --- public API -------------------------------------------------------
    def diagnose(self, incident: dict) -> IncidentDiagnosis:
        # Validate input -> useful diagnostic error, never an empty response.
        if not isinstance(incident, dict):
            return IncidentDiagnosis(
                incident_id="unknown", service="unknown", scenario="unknown",
                status="error", error="Incident payload is not an object.",
            )
        missing = [k for k in ("id", "scenario", "alert") if not incident.get(k)]
        if missing:
            return IncidentDiagnosis(
                incident_id=str(incident.get("id", "unknown")),
                service=str(incident.get("service", "unknown")),
                scenario=str(incident.get("scenario", "unknown")),
                status="error",
                error=f"Incident is missing required field(s): {', '.join(missing)}.",
            )

        scenario = str(incident["scenario"])
        alert = incident.get("alert") or {}
        signals, evidence = detect(incident)

        engine = "deterministic"
        hypotheses = self._deterministic_hypotheses(scenario, signals, evidence)

        # Optional LLM path with deterministic fallback.
        if self._llm is not None:
            try:
                raw = self._llm.propose(
                    {"incident": incident, "signals": sorted(signals)}
                )
                cleaned = validate_llm_hypotheses(raw)
            except Exception:
                cleaned = None
            if cleaned:
                engine = "llm"
                hypotheses = [
                    Hypothesis(
                        cause=h["cause"],
                        confidence=h["confidence"],
                        evidence=h["evidence"],
                        recommended_checks=h["recommended_checks"],
                        missing_information=h["missing_information"],
                    )
                    for h in cleaned
                ]
                hypotheses.sort(key=lambda h: h.confidence, reverse=True)

        symptoms = symptoms_from_signals(signals, evidence)
        top = hypotheses[0]
        summary = (
            f"{str(alert.get('severity','')).upper()} alert on "
            f"{incident.get('service','unknown')}: {alert.get('summary','')} "
            f"Leading hypothesis: {top.cause} ({top.confidence_label} confidence)."
        ).strip()

        return IncidentDiagnosis(
            incident_id=str(incident["id"]),
            service=str(incident.get("service", "unknown")),
            scenario=scenario,
            status="ok",
            summary=summary,
            symptoms=symptoms,
            hypotheses=hypotheses,
            references=self._references(incident),
            engine=engine,
        )


def diagnose_incident(incident: dict, llm: LLMClient | None = None) -> IncidentDiagnosis:
    """Convenience wrapper for a one-off diagnosis."""
    return IncidentAnalyzer(llm=llm).diagnose(incident)
