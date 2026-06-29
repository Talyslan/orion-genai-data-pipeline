"""PDF ingestion routes — POST /api/pdf and GET /api/pdf/help."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from api.guards.corpus_guard import (
    CorpusRejectedError,
    build_pdf_help_response,
    resolve_by_document_id,
    validate_upload,
)
from api.jobs import enqueue_job, get_job_store
from api.schemas import AcceptedResponse, RejectedResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pdf"])

CORPUS_POLICY_HEADER = "aws-well-architected-only"
CORPUS_CATALOG_HEADER = "/api/pdf/help"


class PdfDocumentIdRequest(BaseModel):
    document_id: str


@router.get("/pdf/help")
def get_pdf_help() -> dict[str, Any]:
    """Return AWS PDF corpus instructions and catalog."""
    return build_pdf_help_response()


@router.post(
    "/pdf",
    responses={
        202: {"model": AcceptedResponse},
        403: {"model": RejectedResponse},
        404: {"model": RejectedResponse},
        413: {"model": RejectedResponse},
        422: {"model": RejectedResponse},
        503: {"model": RejectedResponse},
    },
)
async def post_pdf(request: Request) -> JSONResponse:
    """Enqueue an AWS PDF for ingestion (upload or document_id)."""
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        return await _handle_document_id(request)
    if content_type.startswith("multipart/form-data"):
        return await _handle_upload(request)

    return _rejected_response(
        status_code=422,
        error="invalid_request",
        message="Use application/json (document_id) ou multipart/form-data (file).",
        help={
            "summary": "POST /api/pdf aceita dois formatos de entrada.",
            "steps": [
                'JSON: {"document_id": "wellarchitected-framework"}',
                "Upload: multipart com campo file",
                "Consulte GET /api/pdf/help para o catálogo.",
            ],
            "discover": {"help": "/api/pdf/help"},
        },
    )


async def _handle_document_id(request: Request) -> JSONResponse:
    try:
        payload = PdfDocumentIdRequest.model_validate(await request.json())
    except ValidationError as exc:
        return _rejected_response(
            status_code=422,
            error="invalid_request",
            message="Corpo JSON inválido. Informe document_id.",
            help={
                "summary": "O modo document_id exige um JSON com document_id.",
                "steps": [
                    'Exemplo: {"document_id": "wellarchitected-framework"}',
                    "Consulte GET /api/pdf/help para ids válidos.",
                ],
                "discover": {"help": "/api/pdf/help"},
                "detail": str(exc.errors()),
            },
        )

    try:
        document = resolve_by_document_id(payload.document_id)
    except CorpusRejectedError as exc:
        return _corpus_rejected(exc)

    job_input = {
        "mode": "document_id",
        "document_id": document.id,
        "filename": document.filename,
    }
    return _accept_pdf_job(job_input)


async def _handle_upload(request: Request) -> JSONResponse:
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return _rejected_response(
            status_code=422,
            error="invalid_request",
            message="Campo multipart 'file' é obrigatório.",
            help={
                "summary": "Envie o PDF no campo file do multipart/form-data.",
                "steps": [
                    "curl -X POST http://localhost:8000/api/pdf "
                    "-F file=@wellarchitected-framework.pdf",
                    "Consulte GET /api/pdf/help para filenames válidos.",
                ],
                "discover": {"help": "/api/pdf/help"},
            },
        )

    filename = getattr(upload, "filename", None) or "upload.pdf"
    data = await upload.read()

    try:
        document = validate_upload(filename, data)
    except CorpusRejectedError as exc:
        return _corpus_rejected(exc)

    upload_path = _persist_upload(data)
    job_input = {
        "mode": "upload",
        "document_id": document.id,
        "filename": document.filename,
        "upload_path": str(upload_path),
    }
    return _accept_pdf_job(job_input)


def _accept_pdf_job(job_input: dict[str, Any]) -> JSONResponse:
    job = get_job_store().create_job("pdf", job_input)
    enqueue_job(job.job_id)

    body = AcceptedResponse(
        message=("PDF enviado para o pipeline. Acompanhe em GET /api/jobs/{job_id}."),
        job_id=job.job_id,
        type="pdf",
        poll=job.poll_path(),
        input=job_input,
    )
    return _json_with_corpus_headers(body.model_dump(), status_code=202)


def _corpus_rejected(exc: CorpusRejectedError) -> JSONResponse:
    return _rejected_response(
        status_code=exc.http_status,
        error=exc.error_code,
        message=exc.message,
        help=exc.help,
    )


def _rejected_response(
    *,
    status_code: int,
    error: str,
    message: str,
    help: dict[str, Any],
) -> JSONResponse:
    body = RejectedResponse(error=error, message=message, help=help)
    return _json_with_corpus_headers(body.model_dump(), status_code=status_code)


def _json_with_corpus_headers(
    payload: dict[str, Any],
    *,
    status_code: int,
) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content=payload)
    response.headers["X-Corpus-Policy"] = CORPUS_POLICY_HEADER
    response.headers["X-Corpus-Catalog"] = CORPUS_CATALOG_HEADER
    return response


def _persist_upload(data: bytes) -> Path:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as handle:
        handle.write(data)
        return Path(handle.name)
