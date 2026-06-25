"""Tests for the health endpoint and service root."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"]
    assert body["version"]


def test_root_returns_metadata() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"]
    assert body["docs"] == "/docs"
