"""Tests for the incident analysis workflow (KAN-5)."""

import json
from pathlib import Path

from backend.analysis import IncidentAnalyzer, LLMClient, diagnose_incident
from backend.analysis.models import IncidentDiagnosis

REPO = Path(__file__).resolve().parents[1]

# Expected leading cause per scenario (substring match).
EXPECTED_TOP = {
    "high_latency": "downstream dependency",
    "error_rate_spike": "release",
    "pod_crash_loop": "oomkilled",
    "queue_backlog": "stuck consumer",
    "db_saturation": "lock contention",
}


def _incident(scenario: str) -> dict:
    return json.loads((REPO / "sample-data" / "incidents" / f"{scenario}.json").read_text())


def _diagnose(scenario: str) -> IncidentDiagnosis:
    # No RAG references in tests (keep them fast/offline); analyzer handles that.
    return IncidentAnalyzer(retriever=_NoRetriever()).diagnose(_incident(scenario))


class _NoRetriever:
    def retrieve(self, *_args, **_kwargs):
        return []


def test_each_scenario_produces_ranked_hypotheses() -> None:
    """Acceptance: a sample incident produces ranked hypotheses."""
    for scenario in EXPECTED_TOP:
        diag = _diagnose(scenario)
        assert diag.status == "ok"
        assert len(diag.hypotheses) >= 1
        confidences = [h.confidence for h in diag.hypotheses]
        assert confidences == sorted(confidences, reverse=True)


def test_top_hypothesis_matches_expected_cause() -> None:
    for scenario, needle in EXPECTED_TOP.items():
        top = _diagnose(scenario).hypotheses[0]
        assert needle in top.cause.lower(), f"{scenario}: got '{top.cause}'"


def test_hypotheses_have_evidence_and_checks() -> None:
    """Acceptance: each hypothesis includes evidence and recommended checks."""
    diag = _diagnose("db_saturation")
    top = diag.hypotheses[0]
    assert top.evidence, "top hypothesis must cite evidence"
    assert top.recommended_checks, "top hypothesis must recommend checks"
    assert top.confidence_label in {"low", "medium", "high"}


def test_output_is_machine_readable_and_renderable() -> None:
    """Acceptance: output is machine-readable and displayable."""
    diag = _diagnose("high_latency")
    data = json.loads(diag.to_json())
    assert data["hypotheses"][0]["confidence_label"]
    assert "Ranked hypotheses" in diag.to_markdown()


def test_malformed_incident_returns_error_not_empty() -> None:
    """Acceptance: failure cases return a useful diagnostic error."""
    diag = diagnose_incident({"id": "X", "service": "s"})  # no scenario/alert
    assert diag.status == "error"
    assert diag.error and "missing" in diag.error.lower()
    # Not a crash, not an empty/None result.
    assert isinstance(diag.to_dict(), dict)


def test_llm_incomplete_falls_back_to_deterministic() -> None:
    class _BadLLM(LLMClient):
        def propose(self, context):
            return [{"cause": "", "evidence": []}]  # invalid -> rejected

    diag = IncidentAnalyzer(retriever=_NoRetriever(), llm=_BadLLM()).diagnose(
        _incident("pod_crash_loop")
    )
    assert diag.engine == "deterministic"
    assert "oomkilled" in diag.hypotheses[0].cause.lower()


def test_llm_valid_output_is_used() -> None:
    class _GoodLLM(LLMClient):
        def propose(self, context):
            return [{"cause": "Custom LLM cause", "confidence": 0.81, "evidence": ["because"]}]

    diag = IncidentAnalyzer(retriever=_NoRetriever(), llm=_GoodLLM()).diagnose(
        _incident("high_latency")
    )
    assert diag.engine == "llm"
    assert diag.hypotheses[0].cause == "Custom LLM cause"
