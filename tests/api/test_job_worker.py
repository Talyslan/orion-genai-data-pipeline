from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from api.jobs.store import JobStore
from api.jobs.worker import JobWorker
from pipeline.shared.schemas.ingestion_result import IngestionResult
from pipeline.shared.schemas.transform_result import TransformResult


class FakeIngestion:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.local_paths: list[Path] = []
        self.urls: list[str] = []

    def run_local(self, file_path: Path) -> IngestionResult:
        self.local_paths.append(file_path)
        if self.fail:
            raise RuntimeError("ingest failed")
        return IngestionResult(
            source_path=str(file_path),
            local_path=file_path,
            minio_object_key="source/2026/06/28/test.pdf",
            ingested_at=datetime.now(UTC),
            source_format="pdf",
        )

    def run(self, url: str) -> IngestionResult:
        self.urls.append(url)
        if self.fail:
            raise RuntimeError("HTTP 503 ao acessar a URL")
        return IngestionResult(
            source_path=url,
            local_path=Path("data/local/page.md"),
            minio_object_key="source/2026/06/28/welcome.html.md",
            ingested_at=datetime.now(UTC),
            url=url,
        )


class FakeTransform:
    def __init__(self, *, skipped: bool = False) -> None:
        self.skipped = skipped
        self.object_keys: list[str] = []

    def process_object(self, object_key: str) -> TransformResult:
        self.object_keys.append(object_key)
        document_id = uuid4()
        if self.skipped:
            return TransformResult(
                object_key=object_key,
                document_id=document_id,
                skipped=True,
            )
        return TransformResult(
            object_key=object_key,
            document_id=document_id,
            chunks_count=4,
            embeddings_count=4,
        )


def _wait_for_terminal_status(store: JobStore, job_id: str, *, timeout: float = 2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = store.get_job(job_id)
        if job is not None and job.status in {"completed", "skipped", "failed"}:
            return job
        time.sleep(0.02)
    msg = f"Job {job_id} did not finish in time"
    raise AssertionError(msg)


def test_worker_completes_pdf_job(tmp_path: Path) -> None:
    pdf_path = tmp_path / "required.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    store = JobStore(ttl_seconds=3600)
    ingestion = FakeIngestion()
    transform = FakeTransform()
    worker = JobWorker(store=store, ingestion=ingestion, transform=transform)

    job = store.create_job(
        "pdf",
        {
            "mode": "upload",
            "filename": "required.pdf",
            "document_id": "required-doc",
            "upload_path": str(pdf_path),
        },
    )
    worker.submit(job.job_id)
    finished = _wait_for_terminal_status(store, job.job_id)

    assert finished.status == "completed"
    assert finished.result["chunks_count"] == 4
    assert ingestion.local_paths == [pdf_path]
    assert transform.object_keys == ["source/2026/06/28/test.pdf"]
    worker.shutdown(wait=True)


def test_worker_marks_site_job_skipped_when_transform_skips() -> None:
    store = JobStore(ttl_seconds=3600)
    worker = JobWorker(
        store=store,
        ingestion=FakeIngestion(),
        transform=FakeTransform(skipped=True),
    )
    url = "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"
    job = store.create_job("site", {"url": url})

    worker.submit(job.job_id)
    finished = _wait_for_terminal_status(store, job.job_id)

    assert finished.status == "skipped"
    assert finished.reason == "content_unchanged"
    assert (
        finished.result["existing_minio_object_key"]
        == "source/2026/06/28/welcome.html.md"
    )
    worker.shutdown()


def test_worker_marks_failed_job_when_ingestion_raises() -> None:
    store = JobStore(ttl_seconds=3600)
    worker = JobWorker(
        store=store,
        ingestion=FakeIngestion(fail=True),
        transform=FakeTransform(),
    )
    job = store.create_job(
        "site",
        {"url": "https://docs.aws.amazon.com/example"},
    )

    worker.submit(job.job_id)
    finished = _wait_for_terminal_status(store, job.job_id)

    assert finished.status == "failed"
    assert finished.error == "scrape_failed"
    worker.shutdown()
