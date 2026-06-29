from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.jobs.store import JobStore

VALID_URL = "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"
OTHER_VALID_URL = (
    "https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html"
)


@pytest.fixture
def site_route_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    store = JobStore(ttl_seconds=3600)
    enqueued: list[str] = []

    monkeypatch.setattr("api.routes.site.get_job_store", lambda: store)
    monkeypatch.setattr(
        "api.routes.site.enqueue_job",
        lambda job_id: enqueued.append(job_id),
    )

    return {"store": store, "enqueued": enqueued}


def test_site_help_returns_allowed_domains() -> None:
    response = TestClient(app).get("/api/site/help")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy"] == "aws-domains-only"
    assert "docs.aws.amazon.com" in payload["allowed_domains"]
    assert isinstance(payload["sites"], list)


def test_post_site_single_accepted(site_route_env: dict[str, object]) -> None:
    response = TestClient(app).post("/api/site", json={"url": VALID_URL})

    assert response.status_code == 202
    payload = response.json()
    assert payload["enqueued"] is True
    assert payload["type"] == "site"
    assert payload["input"]["url"] == VALID_URL
    assert payload["poll"] == f"/api/jobs/{payload['job_id']}"
    assert site_route_env["enqueued"] == [payload["job_id"]]


def test_post_site_batch_accepted(site_route_env: dict[str, object]) -> None:
    response = TestClient(app).post(
        "/api/site",
        json={"urls": [VALID_URL, OTHER_VALID_URL]},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["enqueued"] is True
    assert payload["total"] == 2
    assert len(payload["jobs"]) == 2
    assert site_route_env["enqueued"] == [
        payload["jobs"][0]["job_id"],
        payload["jobs"][1]["job_id"],
    ]


def test_post_site_rejects_external_domain(site_route_env: dict[str, object]) -> None:
    response = TestClient(app).post(
        "/api/site",
        json={"url": "https://example.com/page"},
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["enqueued"] is False
    assert payload["error"] == "site_domain_not_allowed"
    assert "allowed_domains" in payload["help"]
    assert site_route_env["enqueued"] == []


def test_post_site_rejects_both_url_and_urls(site_route_env: dict[str, object]) -> None:
    response = TestClient(app).post(
        "/api/site",
        json={"url": VALID_URL, "urls": [OTHER_VALID_URL]},
    )

    assert response.status_code == 422
    assert response.json()["enqueued"] is False
    assert response.json()["error"] == "invalid_request"


def test_post_site_batch_rejects_invalid_domain(
    site_route_env: dict[str, object],
) -> None:
    response = TestClient(app).post(
        "/api/site",
        json={"urls": [VALID_URL, "https://example.com/bad"]},
    )

    assert response.status_code == 403
    assert response.json()["enqueued"] is False
    assert site_route_env["enqueued"] == []
