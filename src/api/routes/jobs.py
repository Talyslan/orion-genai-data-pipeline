"""Job monitoring routes — GET /api/jobs and GET /api/jobs/{job_id}."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response

from api.jobs import get_job_store
from api.jobs.store import JobRecord, JobStatus, JobType
from api.schemas import JobListFilters, JobListResponse, JobNotFoundResponse

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    job_type: Annotated[JobType | None, Query(alias="type")] = None,
    status: Annotated[JobStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> JobListResponse:
    """List recent pipeline jobs with optional filters."""
    jobs = get_job_store().list_jobs(job_type=job_type, status=status, limit=limit)
    return JobListResponse(
        jobs=[_job_summary(job) for job in jobs],
        total=len(jobs),
        filters=JobListFilters(type=job_type, status=status, limit=limit),
    )


@router.get(
    "/jobs/{job_id}",
    responses={404: {"model": JobNotFoundResponse}},
)
def get_job(job_id: str, response: Response) -> dict | JobNotFoundResponse:
    """Return the current status and result of a pipeline job."""
    job = get_job_store().get_job(job_id)
    if job is None:
        response.status_code = 404
        return JobNotFoundResponse()
    return _job_detail(job)


def _job_summary(job: JobRecord) -> dict:
    payload = job.to_dict()
    payload["poll"] = job.poll_path()
    return payload


def _job_detail(job: JobRecord) -> dict:
    payload = job.to_dict()
    payload["poll"] = job.poll_path()
    return payload
