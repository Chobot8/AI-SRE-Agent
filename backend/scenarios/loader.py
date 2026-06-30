"""Scenario pack loader and validator (KAN-18).

Pure-ish data access: reads the structured scenario packs under ``scenarios/``,
validates each file against its JSON Schema, and assembles a
``NormalizedIncident``-shaped dict for replay. Heavy/optional imports (jsonschema,
PyYAML, the analysis layer) are kept local to the functions that need them so
importing this module stays cheap.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "scenarios"
SCHEMA_DIR = SCENARIOS_DIR / "schema"

# Every pack must provide exactly these files.
REQUIRED_FILES = (
    "alert.json",
    "logs.jsonl",
    "metrics.json",
    "service_health.json",
    "runbook.md",
    "expected.yaml",
)

# Maps each data file to the schema that validates it.
_FILE_SCHEMAS = {
    "alert.json": "alert.schema.json",
    "metrics.json": "metrics.schema.json",
    "service_health.json": "service_health.schema.json",
    # logs.jsonl is validated line-by-line against logs.schema.json
    # expected.yaml is validated against expected.schema.json
}


class ScenarioError(RuntimeError):
    """Raised when a scenario pack cannot be loaded or is invalid."""


# --- low-level readers -------------------------------------------------------


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScenarioError(f"{path.name} is not valid JSON: {exc}") from exc


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ScenarioError(f"{path.name}:{i} is not valid JSON: {exc}") from exc
    return rows


def _load_yaml(path: Path) -> Any:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ScenarioError(
            "PyYAML is required to read expected.yaml. Install it with "
            "`pip install pyyaml` (it is in requirements.txt)."
        ) from exc
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioError(f"{path.name} is not valid YAML: {exc}") from exc


def _load_schema(name: str) -> dict[str, Any]:
    return _load_json(SCHEMA_DIR / name)


# --- discovery ---------------------------------------------------------------


def pack_dir(slug: str) -> Path:
    return SCENARIOS_DIR / slug


def candidate_packs() -> list[str]:
    """Return every candidate pack directory (any non-``schema`` subdirectory).

    Used by validation so that an incomplete pack (e.g. one still missing
    ``expected.yaml``) is discovered and flagged rather than silently skipped.
    """
    if not SCENARIOS_DIR.exists():
        return []
    return sorted(
        p.name
        for p in SCENARIOS_DIR.iterdir()
        if p.is_dir() and p.name != "schema"
    )


def list_packs() -> list[str]:
    """Return the sorted slugs of every *complete* pack (has ``expected.yaml``).

    This is the loadable/replayable set; use :func:`candidate_packs` when the goal
    is to validate file presence (which must see incomplete directories too).
    """
    return [slug for slug in candidate_packs() if (pack_dir(slug) / "expected.yaml").exists()]


def load_pack(slug: str) -> dict[str, Any]:
    """Load a pack's parsed contents (does not validate; see ``validate_pack``)."""
    d = pack_dir(slug)
    if not d.is_dir():
        raise ScenarioError(f"Unknown scenario pack: {slug!r}")
    return {
        "slug": slug,
        "dir": d,
        "alert": _load_json(d / "alert.json"),
        "metrics": _load_json(d / "metrics.json"),
        "logs": _load_jsonl(d / "logs.jsonl"),
        "service_health": _load_json(d / "service_health.json"),
        "runbook": (d / "runbook.md").read_text(encoding="utf-8"),
        "expected": _load_yaml(d / "expected.yaml"),
    }


# --- validation --------------------------------------------------------------


def validate_pack(slug: str) -> list[str]:
    """Validate a pack's file presence and schemas; return a list of errors.

    An empty list means the pack is valid. Malformed JSON/YAML is reported as a
    validation error (the function never raises for bad pack content), and each
    file is checked independently so one broken file does not hide the others.
    """
    from jsonschema import Draft7Validator

    d = pack_dir(slug)
    if not d.is_dir():
        return [f"{slug}: directory does not exist"]

    errors: list[str] = []

    # 1. File presence (every required file must exist).
    for f in REQUIRED_FILES:
        if not (d / f).exists():
            errors.append(f"{slug}: missing required file {f}")

    def _schema_errors(instance: Any, schema_name: str, label: str) -> None:
        validator = Draft7Validator(_load_schema(schema_name))
        for e in validator.iter_errors(instance):
            loc = "/".join(str(p) for p in e.path) or "<root>"
            errors.append(f"{slug}/{label}: {loc}: {e.message}")

    def _load_or_record(loader_fn, path: Path) -> Any:
        """Parse a file; on failure append an error and return None."""
        try:
            return loader_fn(path)
        except ScenarioError as exc:
            errors.append(f"{slug}/{path.name}: {exc}")
            return None

    # 2. Per-file parse + JSON Schema validation (each file independently).
    parsed: dict[str, Any] = {}
    for filename, schema_name in _FILE_SCHEMAS.items():
        if not (d / filename).exists():
            continue
        instance = _load_or_record(_load_json, d / filename)
        parsed[filename] = instance
        if instance is not None:
            _schema_errors(instance, schema_name, filename)

    # logs.jsonl: validate each line.
    if (d / "logs.jsonl").exists():
        rows = _load_or_record(_load_jsonl, d / "logs.jsonl")
        if rows is not None:
            logs_validator = Draft7Validator(_load_schema("logs.schema.json"))
            for i, row in enumerate(rows, start=1):
                for e in logs_validator.iter_errors(row):
                    errors.append(f"{slug}/logs.jsonl:{i}: {e.message}")

    # expected.yaml.
    expected = None
    if (d / "expected.yaml").exists():
        expected = _load_or_record(_load_yaml, d / "expected.yaml")
        if expected is not None:
            _schema_errors(expected, "expected.schema.json", "expected.yaml")

    # 3. Cross-file consistency (only when both files parsed).
    alert = parsed.get("alert.json")
    if isinstance(expected, dict) and isinstance(alert, dict):
        if expected.get("slug") != slug:
            errors.append(
                f"{slug}/expected.yaml: slug {expected.get('slug')!r} "
                f"does not match folder name {slug!r}"
            )
        if expected.get("id") != alert.get("id"):
            errors.append(
                f"{slug}: expected.yaml id {expected.get('id')!r} != "
                f"alert.json id {alert.get('id')!r}"
            )

    return errors


def validate_all() -> dict[str, list[str]]:
    """Validate every candidate pack; return ``{slug: [errors]}``.

    Iterates :func:`candidate_packs` (all non-schema directories) so an incomplete
    pack missing ``expected.yaml`` is still discovered and flagged.
    """
    return {slug: validate_pack(slug) for slug in candidate_packs()}


# --- replay bridge -----------------------------------------------------------


def _health_log_lines(
    service: str, started_at: str, service_health: dict[str, Any]
) -> list[dict[str, Any]]:
    """Encode a service-health snapshot as schema-valid log entries.

    The ``NormalizedIncident`` contract (incident.schema.json) has no field for
    dependency/health status, so rather than drop ``service_health.json`` we
    surface it through the log channel the agent already reads — keeping the
    dependency evidence reproducible during replay.
    """
    lines: list[dict[str, Any]] = []
    status = service_health.get("status")
    if status:
        lines.append(
            {
                "t": started_at,
                "level": "INFO" if status == "healthy" else "WARN",
                "service": service,
                "message": f"service_health: {service} status={status}",
            }
        )
    for dep in service_health.get("dependencies", []):
        dstatus = dep.get("status")
        parts = [
            f"dependency {dep.get('name')}",
            f"type={dep.get('type')}",
            f"status={dstatus}",
        ]
        if dep.get("latency_ms") is not None:
            parts.append(f"latency_ms={dep['latency_ms']}")
        if dep.get("error_rate") is not None:
            parts.append(f"error_rate={dep['error_rate']}")
        lines.append(
            {
                "t": started_at,
                "level": "INFO" if dstatus == "healthy" else "WARN",
                "service": service,
                "message": " ".join(parts),
            }
        )
    return lines


def to_normalized_incident(pack: dict[str, Any]) -> dict[str, Any]:
    """Assemble a ``NormalizedIncident``-shaped dict from a loaded pack.

    The result conforms to ``sample-data/schema/incident.schema.json`` so a pack
    can flow through the telemetry/analysis/remediation pipeline and the API. The
    service-health snapshot is folded into the log channel (see
    :func:`_health_log_lines`) so dependency evidence is not dropped at replay.
    The pack's ``runbook.md`` is human-facing context; the agent grounds its
    answer on the knowledge base named in ``expected.runbook_references`` via RAG.
    """
    alert = pack["alert"]
    expected = pack["expected"] or {}
    root = expected.get("root_cause", {}) if isinstance(expected, dict) else {}

    expected_root_cause: dict[str, Any] = {
        "summary": root.get("summary", "")
    }
    if root.get("category"):
        expected_root_cause["category"] = root["category"]
    if expected.get("expected_evidence"):
        expected_root_cause["key_signals"] = list(expected["expected_evidence"])
    if expected.get("runbook_references"):
        expected_root_cause["runbook_references"] = list(expected["runbook_references"])

    logs = list(pack["logs"])
    logs += _health_log_lines(
        alert["service"], alert["started_at"], pack.get("service_health") or {}
    )

    return {
        "id": alert["id"],
        "scenario": expected.get("agent_scenario"),
        "service": alert["service"],
        "environment": alert["environment"],
        "alert": {
            "source": alert["source"],
            "severity": alert["severity"],
            "summary": alert["summary"],
            "started_at": alert["started_at"],
            "labels": alert.get("labels", {}),
        },
        "metrics": pack["metrics"]["metrics"],
        "logs": logs,
        "expected_root_cause": expected_root_cause,
    }
