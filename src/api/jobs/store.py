"""In-memory job store for async PDF and site pipeline jobs."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from api.config import api_settings

logger = logging.getLogger(__name__)

JobType = Literal["pdf", "site"]
JobStatus = Literal["pending", "running", "completed", "skipped", "failed"]
JobPhase = Literal["ingest", "transform", "embed"]


@dataclass
class JobRecord:
    job_id: str
    type: JobType
    status: JobStatus
    input: dict[str, Any]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    phase: JobPhase | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    message: str | None = None
    reason: str | None = None
    duration_seconds: float | None = None
    content_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "type": self.type,
            "status": self.status,
            "input": self.input,
            "created_at": _isoformat(self.created_at),
        }
        if self.started_at is not None:
            payload["started_at"] = _isoformat(self.started_at)
        if self.finished_at is not None:
            payload["finished_at"] = _isoformat(self.finished_at)
        if self.phase is not None:
            payload["phase"] = self.phase
        if self.duration_seconds is not None:
            payload["duration_seconds"] = self.duration_seconds
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        if self.message is not None:
            payload["message"] = self.message
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.content_hash is not None:
            payload["content_hash"] = self.content_hash
        if self.type == "site" and "url" in self.input:
            payload["url"] = self.input["url"]
        return payload

    def poll_path(self) -> str:
        return f"/api/jobs/{self.job_id}"


class JobStore:
    """Thread-safe in-memory job registry with TTL."""

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._ttl_seconds = ttl_seconds or api_settings.job_ttl_seconds
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create_job(self, job_type: JobType, input_data: dict[str, Any]) -> JobRecord:
        job = JobRecord(
            job_id=str(uuid4()),
            type=job_type,
            status="pending",
            input=dict(input_data),
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._purge_expired_locked()
            self._jobs[job.job_id] = job
        logger.info("Job created", extra={"job_id": job.job_id, "type": job_type})
        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            self._purge_expired_locked()
            return self._jobs.get(job_id)

    def list_jobs(
        self,
        *,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 20,
    ) -> list[JobRecord]:
        with self._lock:
            self._purge_expired_locked()
            jobs = list(self._jobs.values())

        jobs.sort(key=lambda item: item.created_at, reverse=True)
        if job_type is not None:
            jobs = [job for job in jobs if job.type == job_type]
        if status is not None:
            jobs = [job for job in jobs if job.status == status]
        return jobs[: max(limit, 0)]

    def mark_running(self, job_id: str, *, phase: JobPhase) -> JobRecord:
        return self._update(
            job_id,
            status="running",
            phase=phase,
            started_at=datetime.now(UTC),
        )

    def mark_completed(
        self,
        job_id: str,
        *,
        result: dict[str, Any],
        content_hash: str | None = None,
    ) -> JobRecord:
        return self._finalize(
            job_id,
            status="completed",
            result=result,
            content_hash=content_hash,
        )

    def mark_skipped(
        self,
        job_id: str,
        *,
        reason: str,
        message: str,
        result: dict[str, Any] | None = None,
        content_hash: str | None = None,
    ) -> JobRecord:
        return self._finalize(
            job_id,
            status="skipped",
            reason=reason,
            message=message,
            result=result,
            content_hash=content_hash,
        )

    def mark_failed(
        self,
        job_id: str,
        *,
        error: str,
        message: str,
    ) -> JobRecord:
        return self._finalize(
            job_id,
            status="failed",
            error=error,
            message=message,
        )

    def _finalize(
        self,
        job_id: str,
        *,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        message: str | None = None,
        reason: str | None = None,
        content_hash: str | None = None,
    ) -> JobRecord:
        finished_at = datetime.now(UTC)
        updates: dict[str, Any] = {
            "status": status,
            "finished_at": finished_at,
            "phase": None,
        }
        if result is not None:
            updates["result"] = result
        if error is not None:
            updates["error"] = error
        if message is not None:
            updates["message"] = message
        if reason is not None:
            updates["reason"] = reason
        if content_hash is not None:
            updates["content_hash"] = content_hash

        job = self._update(job_id, **updates)
        if job.started_at is not None:
            duration = (finished_at - job.started_at).total_seconds()
            return self._update(job_id, duration_seconds=duration)
        return job

    def _update(self, job_id: str, **changes: Any) -> JobRecord:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                msg = f"Job not found: {job_id}"
                raise KeyError(msg)
            updated = _replace_job(job, **changes)
            self._jobs[job_id] = updated
            return updated

    def _purge_expired_locked(self) -> None:
        now = datetime.now(UTC)
        expired_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if _is_expired(job, now=now, ttl_seconds=self._ttl_seconds)
        ]
        for job_id in expired_ids:
            del self._jobs[job_id]
            logger.info("Job expired", extra={"job_id": job_id})


_store: JobStore | None = None
_store_lock = threading.Lock()


def get_job_store() -> JobStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = JobStore()
        return _store


def _replace_job(job: JobRecord, **changes: Any) -> JobRecord:
    data = {
        "job_id": job.job_id,
        "type": job.type,
        "status": job.status,
        "input": job.input,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "phase": job.phase,
        "result": job.result,
        "error": job.error,
        "message": job.message,
        "reason": job.reason,
        "duration_seconds": job.duration_seconds,
        "content_hash": job.content_hash,
    }
    data.update(changes)
    return JobRecord(**data)


def _is_expired(job: JobRecord, *, now: datetime, ttl_seconds: int) -> bool:
    anchor = job.finished_at or job.created_at
    return (now - anchor).total_seconds() > ttl_seconds


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
