"""Incident analysis & root-cause hypothesis workflow (KAN-5).

Turns normalized incident context into ranked, evidence-backed root-cause
hypotheses with recommended next checks. Deterministic by default, with an
optional LLM hook and deterministic fallback.
"""

from backend.analysis.llm import LLMClient, validate_llm_hypotheses
from backend.analysis.models import Hypothesis, IncidentDiagnosis
from backend.analysis.pipeline import IncidentAnalyzer, diagnose_incident

__all__ = [
    "Hypothesis",
    "IncidentDiagnosis",
    "IncidentAnalyzer",
    "diagnose_incident",
    "LLMClient",
    "validate_llm_hypotheses",
]
