from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.schemas import HealthComponentStatus, HealthResponse


def test_health_returns_ok_when_all_checks_pass(monkeypatch) -> None:
    def _all_ok() -> HealthResponse:
        ok = HealthComponentStatus(status="ok")
        return HealthResponse(
            status="ok",
            checks={"minio": ok, "postgres": ok, "qdrant": ok},
        )

    monkeypatch.setattr("api.routes.health.run_health_checks", _all_ok)

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["minio"]["status"] == "ok"


def test_health_returns_503_when_degraded(monkeypatch) -> None:
    def _degraded() -> HealthResponse:
        return HealthResponse(
            status="degraded",
            checks={
                "minio": HealthComponentStatus(status="ok"),
                "postgres": HealthComponentStatus(
                    status="error",
                    message="connection refused",
                ),
                "qdrant": HealthComponentStatus(status="ok"),
            },
        )

    monkeypatch.setattr("api.routes.health.run_health_checks", _degraded)

    response = TestClient(app).get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["postgres"]["message"] == "connection refused"


def test_openapi_is_served_under_api_prefix() -> None:
    response = TestClient(app).get("/api/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["title"] == "Orion Pipeline API"
    assert "/api/health" in payload["paths"]


def test_swagger_docs_are_available() -> None:
    response = TestClient(app).get("/api/docs")

    assert response.status_code == 200
    assert "swagger" in response.text.lower()
