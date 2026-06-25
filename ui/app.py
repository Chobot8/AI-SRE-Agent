"""Streamlit incident triage UI for the AI SRE Agent (KAN-8)."""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st


DEFAULT_API_BASE_URL = "http://localhost:8000"
REQUEST_TIMEOUT_SECONDS = 10.0


def _api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _get_json(base_url: str, path: str) -> dict[str, Any]:
    response = httpx.get(_api_url(base_url, path), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _post_json(base_url: str, path: str) -> dict[str, Any]:
    response = httpx.post(_api_url(base_url, path), timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def load_scenarios(base_url: str) -> list[str]:
    body = _get_json(base_url, "/scenarios")
    return [item["scenario"] for item in body.get("scenarios", []) if "scenario" in item]


def run_scenario(base_url: str, scenario: str) -> dict[str, Any]:
    receipt = _post_json(base_url, f"/incidents/replay/{scenario}")
    diagnosis_id = receipt.get("diagnosis_id")
    if not diagnosis_id:
        raise RuntimeError("Replay response did not include a diagnosis_id.")
    return _get_json(base_url, f"/diagnoses/{diagnosis_id}")


def render_evidence(hypotheses: list[dict[str, Any]]) -> None:
    evidence_items: list[str] = []
    for hypothesis in hypotheses:
        for evidence in hypothesis.get("evidence", []):
            if evidence not in evidence_items:
                evidence_items.append(evidence)

    st.subheader("Evidence")
    if not evidence_items:
        st.info("No evidence returned for this diagnosis.")
        return

    for evidence in evidence_items:
        st.markdown(f"- {evidence}")


def render_hypotheses(hypotheses: list[dict[str, Any]]) -> None:
    st.subheader("Root-Cause Hypotheses")
    if not hypotheses:
        st.info("No hypotheses returned for this diagnosis.")
        return

    for index, hypothesis in enumerate(hypotheses, start=1):
        label = hypothesis.get("confidence_label", "unknown")
        confidence = hypothesis.get("confidence") or 0
        title = hypothesis.get("cause", "Untitled hypothesis")
        with st.expander(f"{index}. {title} ({label}, {confidence:.0%})", expanded=index == 1):
            checks = hypothesis.get("recommended_checks", [])
            missing = hypothesis.get("missing_information", [])

            if checks:
                st.markdown("**Recommended checks**")
                for check in checks:
                    st.markdown(f"- {check}")
            if missing:
                st.markdown("**Missing information**")
                for item in missing:
                    st.markdown(f"- {item}")


def render_recommendations(remediation: dict[str, Any]) -> None:
    st.subheader("Remediation Recommendations")
    recommendations = remediation.get("recommendations", [])
    if not recommendations:
        st.info("No remediation recommendations returned.")
        return

    for recommendation in recommendations:
        risk = recommendation.get("risk", "unknown")
        approval = recommendation.get("approval_required", False)
        title = recommendation.get("title", "Untitled recommendation")
        label = f"{title} | risk: {risk}"
        if approval:
            label += " | approval required"

        with st.container(border=True):
            st.markdown(f"**{label}**")
            st.write(recommendation.get("rationale", "No rationale provided."))
            if recommendation.get("rollback_note"):
                st.caption(f"Rollback: {recommendation['rollback_note']}")
            if recommendation.get("evidence"):
                st.markdown("Evidence")
                for evidence in recommendation["evidence"]:
                    st.markdown(f"- {evidence}")


def render_diagnosis(diagnosis: dict[str, Any]) -> None:
    status = diagnosis.get("status", "unknown")
    if status != "ok":
        st.error(diagnosis.get("error", "Diagnosis returned a non-ok status."))
        return

    st.subheader("Incident Summary")
    st.write(diagnosis.get("summary", "No summary returned."))

    col1, col2, col3 = st.columns(3)
    col1.metric("Incident", diagnosis.get("incident_id", "unknown"))
    col2.metric("Service", diagnosis.get("service", "unknown"))
    col3.metric("Engine", diagnosis.get("engine", "unknown"))

    hypotheses = diagnosis.get("hypotheses", [])
    render_evidence(hypotheses)
    render_hypotheses(hypotheses)
    render_recommendations(diagnosis.get("remediation", {}))

    with st.expander("Raw API response"):
        st.json(diagnosis)


def main() -> None:
    st.set_page_config(page_title="AI SRE Agent", layout="wide")
    st.title("AI SRE Agent")
    st.caption("Replay a sample incident and review the diagnosis, evidence, and safe remediation plan.")

    with st.sidebar:
        st.header("Runbook Demo")
        base_url = st.text_input("Backend API URL", DEFAULT_API_BASE_URL)
        st.caption("Start the backend with `uvicorn backend.main:app --reload`.")

    try:
        scenarios = load_scenarios(base_url)
    except httpx.HTTPError as exc:
        st.error(f"Could not reach the backend API at {base_url}: {exc}")
        st.stop()
    except ValueError as exc:
        st.error(f"Backend returned invalid JSON: {exc}")
        st.stop()

    if not scenarios:
        st.warning("No sample scenarios are available from the backend.")
        st.stop()

    scenario = st.selectbox("Incident scenario", scenarios)
    if "diagnosis" not in st.session_state:
        st.session_state.diagnosis = None

    if st.button("Run diagnosis", type="primary"):
        with st.spinner(f"Diagnosing {scenario}..."):
            try:
                st.session_state.diagnosis = run_scenario(base_url, scenario)
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                st.error(f"Backend returned HTTP {exc.response.status_code}: {detail}")
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                st.error(f"Could not run diagnosis: {exc}")

    if st.session_state.diagnosis is None:
        st.info("Select a scenario and run a diagnosis to see the agent output.")
    else:
        render_diagnosis(st.session_state.diagnosis)


if __name__ == "__main__":
    main()
