"""Background worker for PDF and site pipeline jobs."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from api.jobs.store import JobRecord, JobStore, get_job_store
from pipeline.ingestion.pipeline import IngestionPipeline
from pipeline.shared.config import settings
from pipeline.transform.pipeline import TransformPipeline

if TYPE_CHECKING:
    from pipeline.shared.schemas.ingestion_result import IngestionResult
    from pipeline.shared.schemas.transform_result import TransformResult

logger = logging.getLogger(__name__)


class JobWorker:
    """Runs ingestion and transformation jobs on a background thread pool."""

    def __init__(
        self,
        store: JobStore | None = None,
        ingestion: IngestionPipeline | None = None,
        transform: TransformPipeline | None = None,
        *,
        max_workers: int = 1,
    ) -> None:
        self._store = store or get_job_store()
        self._ingestion = ingestion or IngestionPipeline()
        self._transform = transform or TransformPipeline()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pipeline-job",
        )

    def submit(self, job_id: str) -> None:
        self._executor.submit(self._process_job, job_id)

    def shutdown(self, *, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _process_job(self, job_id: str) -> None:
        job = self._store.get_job(job_id)
        if job is None or job.status != "pending":
            return

        upload_path: Path | None = None
        try:
            if job.type == "pdf":
                upload_path = _maybe_upload_path(job)
                self._process_pdf(job, upload_path=upload_path)
            elif job.type == "site":
                self._process_site(job)
            else:
                self._store.mark_failed(
                    job_id,
                    error="unsupported_job_type",
                    message=f"Tipo de job não suportado: {job.type}",
                )
        except Exception as exc:
            logger.exception("Job failed", extra={"job_id": job_id})
            self._store.mark_failed(
                job_id,
                error=_classify_error(exc, job),
                message=str(exc),
            )
        finally:
            if upload_path is not None and upload_path.is_file():
                upload_path.unlink(missing_ok=True)

    def _process_pdf(self, job: JobRecord, *, upload_path: Path | None) -> None:
        pdf_path = upload_path or _resolve_pdf_path(job)
        self._store.mark_running(job.job_id, phase="ingest")
        ingest_result = self._ingestion.run_local(pdf_path)
        self._run_transform(job, ingest_result)

    def _process_site(self, job: JobRecord) -> None:
        url = job.input["url"]
        self._store.mark_running(job.job_id, phase="ingest")
        ingest_result = self._ingestion.run(url)
        self._run_transform(job, ingest_result)

    def _run_transform(
        self,
        job: JobRecord,
        ingest_result: IngestionResult,
    ) -> None:
        self._store.mark_running(job.job_id, phase="transform")
        object_key = ingest_result.minio_object_key
        transform_result = self._transform.process_object(object_key)
        self._finalize_transform(job, ingest_result, transform_result)

    def _finalize_transform(
        self,
        job: JobRecord,
        ingest_result: IngestionResult,
        transform_result: TransformResult,
    ) -> None:
        if transform_result.skipped:
            self._store.mark_skipped(
                job.job_id,
                reason="content_unchanged",
                message="O conteúdo já foi processado (hash idêntico).",
                result={
                    "existing_minio_object_key": ingest_result.minio_object_key,
                    "document_id": (
                        str(transform_result.document_id)
                        if transform_result.document_id
                        else None
                    ),
                },
            )
            return

        self._store.mark_completed(
            job.job_id,
            result={
                "minio_object_key": ingest_result.minio_object_key,
                "document_id": str(transform_result.document_id),
                "chunks_count": transform_result.chunks_count,
                "embeddings_count": transform_result.embeddings_count,
            },
        )


_worker: JobWorker | None = None
_worker_lock = threading.Lock()


def get_job_worker() -> JobWorker:
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = JobWorker()
        return _worker


def enqueue_job(job_id: str) -> None:
    get_job_worker().submit(job_id)


def _resolve_pdf_path(job: JobRecord) -> Path:
    filename = job.input.get("filename")
    if not filename:
        msg = "PDF job input missing filename"
        raise ValueError(msg)
    return Path(settings.pdf_download_dir) / str(filename)


def _maybe_upload_path(job: JobRecord) -> Path | None:
    if job.input.get("mode") != "upload":
        return None
    upload_path = job.input.get("upload_path")
    if not upload_path:
        msg = "Upload PDF job missing upload_path"
        raise ValueError(msg)
    return Path(upload_path)


def _classify_error(exc: Exception, job: JobRecord) -> str:
    if job.type == "site" and "scrape" in exc.__class__.__name__.lower():
        return "scrape_failed"
    if "HTTP" in str(exc):
        return "scrape_failed"
    return "pipeline_error"
