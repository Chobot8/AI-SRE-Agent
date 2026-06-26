"""Evaluation dataset tests (KAN-9)."""

import json
from pathlib import Path

from backend.analysis import IncidentAnalyzer
from backend.rag import Retriever, build_index
from backend.telemetry.schema import NormalizedIncident

REPO = Path(__file__).resolve().parents[1]
INCIDENTS = REPO / "sample-data" / "incidents"
RUNBOOKS = REPO / "knowledge" / "runbooks"
BASELINE = REPO / "sample-data" / "evaluation" / "baseline.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _baseline() -> dict:
    return _load_json(BASELINE)


def _incident(scenario: str) -> dict:
    return _load_json(INCIDENTS / f"{scenario}.json")


def test_evaluation_baseline_covers_all_sample_incidents() -> None:
    """Acceptance: at least five incident scenarios exist and are in the baseline."""
    baseline = _baseline()
    incident_names = {p.stem for p in INCIDENTS.glob("*.json")}
    baseline_names = set(baseline["scenarios"])

    assert len(incident_names) >= baseline["minimum_scenarios"] >= 5
    assert incident_names == baseline_names


def test_sample_incidents_have_expected_root_cause_and_evidence() -> None:
    """Acceptance: every scenario has expected cause, signals, and runbook references."""
    baseline = _baseline()
    for scenario, expectation in baseline["scenarios"].items():
        incident = NormalizedIncident.model_validate(_incident(scenario))
        expected = incident.expected_root_cause

        assert expected is not None, scenario
        assert expected.summary, scenario
        assert expected.category == expectation["expected_category"]
        assert len(expected.key_signals) >= 3, scenario
        assert expectation["expected_runbook"] in expected.runbook_references
        for runbook in expected.runbook_references:
            assert (RUNBOOKS / runbook).exists(), f"{scenario}: missing {runbook}"

        assert incident.alert.summary
        assert incident.metrics and all(metric.points for metric in incident.metrics)
        assert incident.logs


def test_retrieval_quality_matches_expected_runbooks() -> None:
    """Acceptance: each evaluation incident retrieves its matching runbook first."""
    retriever = Retriever(build_index())
    for scenario, expectation in _baseline()["scenarios"].items():
        hits = retriever.retrieve_for_incident(_incident(scenario), k=3)

        assert hits, scenario
        assert hits[0].chunk.source == expectation["expected_runbook"], scenario
        assert hits[0].score > 0, scenario


def test_diagnosis_baseline_completeness() -> None:
    """Acceptance: baseline diagnosis is complete enough to track future changes."""
    baseline = _baseline()
    analyzer = IncidentAnalyzer(retriever=Retriever(build_index()))
    min_confidence = baseline["minimum_top_hypothesis_confidence"]

    for scenario, expectation in baseline["scenarios"].items():
        diagnosis = analyzer.diagnose(_incident(scenario))
        top = diagnosis.hypotheses[0]

        assert diagnosis.status == "ok", scenario
        assert diagnosis.summary, scenario
        assert diagnosis.symptoms, scenario
        assert expectation["expected_top_cause_contains"] in top.cause.lower(), scenario
        assert top.confidence >= min_confidence, scenario
        assert top.evidence, scenario
        assert top.recommended_checks, scenario
        assert diagnosis.references, scenario
        assert any(expectation["expected_runbook"] in ref for ref in diagnosis.references), scenario
