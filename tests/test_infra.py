"""Guard tests for the containerized demo stack (KAN-10).

These do not require Docker. They assert that the infra assets exist, are wired
correctly (services, health checks, dependency ordering), that configuration is
externalized via environment variables, and that no secrets are committed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INFRA = REPO_ROOT / "infra"
COMPOSE_FILE = INFRA / "docker-compose.yml"
BACKEND_DOCKERFILE = INFRA / "Dockerfile.backend"
UI_DOCKERFILE = INFRA / "Dockerfile.ui"


def test_infra_files_exist() -> None:
    assert COMPOSE_FILE.is_file()
    assert BACKEND_DOCKERFILE.is_file()
    assert UI_DOCKERFILE.is_file()
    assert (REPO_ROOT / ".dockerignore").is_file()


def test_dockerfiles_define_healthchecks_and_startup() -> None:
    backend = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
    ui = UI_DOCKERFILE.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in backend
    assert "/health" in backend
    assert "uvicorn backend.main:app" in backend

    assert "HEALTHCHECK" in ui
    assert "/_stcore/health" in ui
    # CMD uses exec form: ["streamlit", "run", "ui/app.py"].
    assert "streamlit" in ui and "ui/app.py" in ui


def _load_compose() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def test_compose_is_valid_yaml_with_both_services() -> None:
    compose = _load_compose()
    services = compose.get("services", {})
    assert "api" in services
    assert "ui" in services


def test_compose_services_have_healthchecks() -> None:
    services = _load_compose()["services"]
    for name in ("api", "ui"):
        assert "healthcheck" in services[name], f"{name} missing healthcheck"
        assert services[name]["healthcheck"].get("test")


def test_ui_waits_for_api_health() -> None:
    ui = _load_compose()["services"]["ui"]
    depends = ui.get("depends_on", {})
    assert "api" in depends
    assert depends["api"].get("condition") == "service_healthy"


def test_config_is_externalized_via_env() -> None:
    services = _load_compose()["services"]
    # UI backend URL is supplied through the environment, not hard-coded.
    assert services["ui"]["environment"]["BACKEND_API_URL"] == "http://api:8000"
    app_py = (REPO_ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    assert 'os.environ.get("BACKEND_API_URL"' in app_py


def test_no_secrets_committed() -> None:
    # Only the template is tracked; the real .env must never be committed.
    assert (REPO_ROOT / ".env.example").is_file()
    assert not (REPO_ROOT / ".env").exists(), ".env must not be committed"

    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in env_example.splitlines():
        if line.startswith(("OPENAI_API_KEY", "ANTHROPIC_API_KEY")):
            # Keys are present as blank placeholders only.
            assert line.split("=", 1)[1].strip() == ""
