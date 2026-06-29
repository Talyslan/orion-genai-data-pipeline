from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api.jobs.store import JobStore, _replace_job


def test_create_job_starts_pending() -> None:
    store = JobStore(ttl_seconds=3600)
    job = store.create_job("pdf", {"filename": "required.pdf"})

    assert job.status == "pending"
    assert job.type == "pdf"
    assert job.poll_path() == f"/api/jobs/{job.job_id}"


def test_list_jobs_filters_by_type_and_status() -> None:
    store = JobStore(ttl_seconds=3600)
    pdf_job = store.create_job("pdf", {"filename": "a.pdf"})
    site_job = store.create_job("site", {"url": "https://docs.aws.amazon.com/a"})

    store.mark_completed(pdf_job.job_id, result={"minio_object_key": "source/a.pdf"})
    store.mark_failed(
        site_job.job_id,
        error="scrape_failed",
        message="timeout",
    )

    pdf_jobs = store.list_jobs(job_type="pdf", status="completed")
    failed_jobs = store.list_jobs(status="failed", limit=10)

    assert len(pdf_jobs) == 1
    assert pdf_jobs[0].job_id == pdf_job.job_id
    assert len(failed_jobs) == 1
    assert failed_jobs[0].job_id == site_job.job_id


def test_mark_running_sets_phase_and_started_at() -> None:
    store = JobStore(ttl_seconds=3600)
    job = store.create_job("site", {"url": "https://docs.aws.amazon.com/a"})

    running = store.mark_running(job.job_id, phase="ingest")

    assert running.status == "running"
    assert running.phase == "ingest"
    assert running.started_at is not None


def test_mark_completed_sets_duration_and_result() -> None:
    store = JobStore(ttl_seconds=3600)
    job = store.create_job("pdf", {"filename": "a.pdf"})
    store.mark_running(job.job_id, phase="transform")

    completed = store.mark_completed(
        job.job_id,
        result={"chunks_count": 3, "embeddings_count": 3},
    )

    assert completed.status == "completed"
    assert completed.result == {"chunks_count": 3, "embeddings_count": 3}
    assert completed.duration_seconds is not None
    assert completed.finished_at is not None


def test_get_job_returns_none_after_ttl() -> None:
    store = JobStore(ttl_seconds=60)
    job = store.create_job("pdf", {"filename": "a.pdf"})
    expired = _replace_job(
        job,
        created_at=datetime.now(UTC) - timedelta(seconds=120),
    )
    store._jobs[job.job_id] = expired

    assert store.get_job(job.job_id) is None


def test_job_to_dict_includes_poll_fields() -> None:
    store = JobStore(ttl_seconds=3600)
    job = store.create_job(
        "site",
        {
            "url": "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"
        },
    )

    payload = job.to_dict()

    assert payload["type"] == "site"
    assert payload["url"] == job.input["url"]
    assert payload["created_at"].endswith("Z")
