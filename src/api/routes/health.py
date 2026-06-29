"""Health endpoint for infrastructure probes."""

from __future__ import annotations

from fastapi import APIRouter, Response

from api.health_checks import run_health_checks
from api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(response: Response) -> HealthResponse:
    """Return connectivity status for MinIO, PostgreSQL and Qdrant."""
    result = run_health_checks()
    if result.status != "ok":
        response.status_code = 503
    return result
