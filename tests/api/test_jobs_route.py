from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.jobs.store import JobStore


@pytest.fixture
def jobs_route_env(monkeypatch: pytest.MonkeyPatch) -> JobStore:
    store = JobStore(ttl_seconds=3600)
    monkeypatch.setattr("api.routes.jobs.get_job_store", lambda: store)
    return store


def test_list_jobs_returns_recent_jobs(jobs_route_env: JobStore) -> None:
    pdf_job = jobs_route_env.create_job("pdf", {"filename": "a.pdf"})
    site_job = jobs_route_env.create_job(
        "site",
        {
            "url": "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"
        },
    )
    jobs_route_env.mark_completed(pdf_job.job_id, result={"chunks_count": 1})

    response = TestClient(app).get("/api/jobs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["filters"]["limit"] == 20
    assert {item["job_id"] for item in payload["jobs"]} == {
        pdf_job.job_id,
        site_job.job_id,
    }
    assert all("poll" in item for item in payload["jobs"])


def test_list_jobs_filters_by_type_and_status(jobs_route_env: JobStore) -> None:
    pdf_job = jobs_route_env.create_job("pdf", {"filename": "a.pdf"})
    jobs_route_env.create_job(
        "site",
        {"url": "https://docs.aws.amazon.com/example"},
    )
    jobs_route_env.mark_running(pdf_job.job_id, phase="ingest")

    response = TestClient(app).get(
        "/api/jobs",
        params={"type": "pdf", "status": "running", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["jobs"][0]["job_id"] == pdf_job.job_id
    assert payload["filters"] == {
        "type": "pdf",
        "status": "running",
        "limit": 5,
    }


def test_get_job_returns_detail(jobs_route_env: JobStore) -> None:
    job = jobs_route_env.create_job("pdf", {"filename": "a.pdf"})
    jobs_route_env.mark_completed(
        job.job_id,
        result={"minio_object_key": "source/a.pdf", "chunks_count": 3},
    )

    response = TestClient(app).get(f"/api/jobs/{job.job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result"]["chunks_count"] == 3
    assert payload["poll"] == f"/api/jobs/{job.job_id}"


def test_get_job_returns_404_when_missing(jobs_route_env: JobStore) -> None:
    response = TestClient(app).get("/api/jobs/missing-job-id")

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "not_found"
    assert "TTL" in payload["message"]


def test_get_job_returns_404_when_expired(jobs_route_env: JobStore) -> None:
    from datetime import UTC, datetime, timedelta

    from api.jobs.store import _replace_job

    job = jobs_route_env.create_job("site", {"url": "https://docs.aws.amazon.com/a"})
    jobs_route_env._jobs[job.job_id] = _replace_job(
        job,
        created_at=datetime.now(UTC) - timedelta(seconds=7200),
    )

    response = TestClient(app).get(f"/api/jobs/{job.job_id}")

    assert response.status_code == 404
