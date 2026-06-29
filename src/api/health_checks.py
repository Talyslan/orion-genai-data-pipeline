"""Infrastructure health probes for GET /api/health."""

from __future__ import annotations

import logging

import psycopg
from minio import Minio
from qdrant_client import QdrantClient

from api.schemas import HealthComponentStatus, HealthResponse
from pipeline.shared.config import settings

logger = logging.getLogger(__name__)


def run_health_checks() -> HealthResponse:
    """Probe MinIO, PostgreSQL and Qdrant."""
    checks = {
        "minio": _check_minio(),
        "postgres": _check_postgres(),
        "qdrant": _check_qdrant(),
    }
    all_ok = all(item.status == "ok" for item in checks.values())
    overall = "ok" if all_ok else "degraded"
    return HealthResponse(status=overall, checks=checks)


def _check_minio() -> HealthComponentStatus:
    try:
        client = Minio(
            settings.minio_url,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        client.bucket_exists(settings.minio_bucket)
        return HealthComponentStatus(status="ok")
    except Exception as exc:
        logger.warning("MinIO health check failed", exc_info=exc)
        return HealthComponentStatus(status="error", message=str(exc))


def _check_postgres() -> HealthComponentStatus:
    try:
        with psycopg.connect(settings.postgres_url, connect_timeout=5) as conn:
            conn.execute("SELECT 1")
        return HealthComponentStatus(status="ok")
    except Exception as exc:
        logger.warning("PostgreSQL health check failed", exc_info=exc)
        return HealthComponentStatus(status="error", message=str(exc))


def _check_qdrant() -> HealthComponentStatus:
    try:
        client = QdrantClient(url=settings.qdrant_url, timeout=5)
        client.get_collections()
        return HealthComponentStatus(status="ok")
    except Exception as exc:
        logger.warning("Qdrant health check failed", exc_info=exc)
        return HealthComponentStatus(status="error", message=str(exc))
