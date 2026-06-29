"""Site ingestion routes — POST /api/site and GET /api/site/help."""

from __future__ import annotations

from typing import Any, Self

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, model_validator

from api.guards.site_guard import (
    SiteRejectedError,
    build_site_help_response,
    validate_site_url,
    validate_site_urls,
)
from api.jobs import enqueue_job, get_job_store
from api.schemas import (
    AcceptedResponse,
    RejectedResponse,
    SiteBatchAcceptedResponse,
    SiteJobAcceptedItem,
)

router = APIRouter(tags=["site"])

VALID_AWS_URL = (
    "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"
)


class SiteSubmitRequest(BaseModel):
    url: str | None = None
    urls: list[str] | None = None

    @model_validator(mode="after")
    def validate_exclusive_fields(self) -> Self:
        has_url = bool(self.url and self.url.strip())
        has_urls = bool(self.urls)
        if has_url and has_urls:
            msg = "Informe apenas url ou urls, não ambos."
            raise ValueError(msg)
        if not has_url and not has_urls:
            msg = "Informe url (single) ou urls (batch)."
            raise ValueError(msg)
        if self.urls is not None and len(self.urls) == 0:
            msg = "A lista urls não pode ser vazia."
            raise ValueError(msg)
        return self


@router.get("/site/help")
def get_site_help() -> dict[str, Any]:
    """Return AWS site allowlist instructions and catalog."""
    return build_site_help_response()


@router.post(
    "/site",
    responses={
        202: {"description": "Accepted"},
        403: {"model": RejectedResponse},
        422: {"model": RejectedResponse},
    },
)
async def post_site(request: Request) -> JSONResponse:
    """Enqueue one or more AWS site URLs for scraping and ingestion."""
    try:
        body = SiteSubmitRequest.model_validate(await request.json())
    except ValidationError as exc:
        return _rejected(
            status_code=422,
            error="invalid_request",
            message="Corpo JSON inválido. Use url ou urls.",
            help={
                "summary": "POST /api/site aceita url (single) ou urls (batch).",
                "steps": [
                    f'Single: {{"url": "{VALID_AWS_URL}"}}',
                    f'Batch: {{"urls": ["{VALID_AWS_URL}"]}}',
                    "Consulte GET /api/site/help para URLs recomendadas.",
                ],
                "discover": {"help": "/api/site/help"},
                "detail": str(exc.errors()),
            },
        )

    if body.url is not None:
        return _accept_single(body.url)
    assert body.urls is not None
    return _accept_batch(body.urls)


def _accept_single(url: str) -> JSONResponse:
    try:
        validated_url = validate_site_url(url)
    except SiteRejectedError as exc:
        return _site_rejected(exc)

    job = get_job_store().create_job("site", {"url": validated_url})
    enqueue_job(job.job_id)

    payload = AcceptedResponse(
        message="URL enviada para o pipeline.",
        job_id=job.job_id,
        type="site",
        poll=job.poll_path(),
        input={"url": validated_url},
    )
    return JSONResponse(status_code=202, content=payload.model_dump())


def _accept_batch(urls: list[str]) -> JSONResponse:
    try:
        validated_urls = validate_site_urls(urls)
    except SiteRejectedError as exc:
        return _site_rejected(exc)

    store = get_job_store()
    jobs: list[SiteJobAcceptedItem] = []
    for validated_url in validated_urls:
        job = store.create_job("site", {"url": validated_url})
        enqueue_job(job.job_id)
        jobs.append(
            SiteJobAcceptedItem(
                job_id=job.job_id,
                poll=job.poll_path(),
                input={"url": validated_url},
            )
        )

    payload = SiteBatchAcceptedResponse(
        message=f"{len(jobs)} URL(s) enviada(s) para o pipeline.",
        jobs=jobs,
        total=len(jobs),
    )
    return JSONResponse(status_code=202, content=payload.model_dump())


def _site_rejected(exc: SiteRejectedError) -> JSONResponse:
    body = RejectedResponse(
        error=exc.error_code,
        message=exc.message,
        help=exc.help,
    )
    return JSONResponse(status_code=exc.http_status, content=body.model_dump())


def _rejected(
    *,
    status_code: int,
    error: str,
    message: str,
    help: dict[str, Any],
) -> JSONResponse:
    body = RejectedResponse(error=error, message=message, help=help)
    return JSONResponse(status_code=status_code, content=body.model_dump())
