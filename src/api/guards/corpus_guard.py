"""AWS PDF corpus allowlist and upload validation for POST /api/pdf."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from api.config import api_settings
from pipeline.ingestion.corpus import CorpusDocument, check_corpus, load_manifest
from pipeline.ingestion.corpus_download import file_sha256, validate_pdf_bytes
from pipeline.shared.config.settings import settings

UNSAFE_FILENAME = re.compile(r"(?:\.\.|[/\\])")


@dataclass(frozen=True)
class CorpusRejectedError(Exception):
    error_code: str
    http_status: int
    message: str
    help: dict

    def __str__(self) -> str:
        return self.message


def build_reference_hashes(
    manifest_path: Path | str | None = None,
    corpus_dir: Path | str | None = None,
) -> dict[str, str]:
    """Map manifest filename to SHA-256 (manifest field, then local file)."""
    resolved_manifest = Path(manifest_path or settings.pdf_manifest_path).resolve()
    resolved_dir = Path(corpus_dir or settings.pdf_download_dir).resolve()
    documents = load_manifest(resolved_manifest)

    hashes: dict[str, str] = {}
    for document in documents:
        if document.sha256:
            hashes[document.filename] = document.sha256

    for document in documents:
        if document.filename in hashes:
            continue
        local_path = resolved_dir / document.filename
        if local_path.is_file():
            hashes[document.filename] = file_sha256(local_path)

    return hashes


def resolve_by_document_id(
    document_id: str,
    *,
    manifest_path: Path | str | None = None,
    corpus_dir: Path | str | None = None,
) -> CorpusDocument:
    """Resolve a manifest document_id to a local corpus entry."""
    resolved_manifest = Path(manifest_path or settings.pdf_manifest_path).resolve()
    resolved_dir = Path(corpus_dir or settings.pdf_download_dir).resolve()
    documents = load_manifest(resolved_manifest)

    document = next((doc for doc in documents if doc.id == document_id), None)
    if document is None:
        raise _reject(
            error_code="pdf_not_in_corpus",
            http_status=403,
            message=(
                f"O document_id '{document_id}' não faz parte do corpus AWS aceito."
            ),
            filename=None,
            document_id=document_id,
        )

    if document.optional and not api_settings.allow_optional_corpus:
        raise _reject(
            error_code="pdf_optional_disabled",
            http_status=403,
            message=(
                f"O documento '{document_id}' é opcional e não está "
                "habilitado nesta API."
            ),
            filename=document.filename,
            document_id=document_id,
        )

    local_path = resolved_dir / document.filename
    if not local_path.is_file():
        raise _reject(
            error_code="pdf_file_not_found",
            http_status=404,
            message=(
                f"O PDF '{document.filename}' não está disponível no servidor. "
                "Execute download-corpus ou monte o volume ./pdfs."
            ),
            filename=document.filename,
            document_id=document_id,
        )

    try:
        _validate_pdf_content(local_path.read_bytes())
    except ValueError as exc:
        raise _reject(
            error_code="invalid_pdf",
            http_status=422,
            message=f"O arquivo local '{document.filename}' não é um PDF válido.",
            filename=document.filename,
            document_id=document_id,
            detail=str(exc),
        ) from exc

    return document


def validate_upload(
    filename: str,
    data: bytes,
    *,
    manifest_path: Path | str | None = None,
    corpus_dir: Path | str | None = None,
) -> CorpusDocument:
    """Validate an uploaded PDF against the AWS corpus allowlist."""
    resolved_manifest = Path(manifest_path or settings.pdf_manifest_path).resolve()
    resolved_dir = Path(corpus_dir or settings.pdf_download_dir).resolve()
    documents = load_manifest(resolved_manifest)
    documents_by_filename = {doc.filename: doc for doc in documents}

    safe_name = _sanitize_filename(filename)
    if safe_name is None:
        raise _reject(
            error_code="invalid_filename",
            http_status=403,
            message="Nome de arquivo inválido ou inseguro.",
            filename=filename,
        )

    if len(data) > api_settings.pdf_max_upload_bytes:
        raise _reject(
            error_code="file_too_large",
            http_status=413,
            message=(
                f"O arquivo excede o limite de "
                f"{api_settings.pdf_max_upload_bytes} bytes."
            ),
            filename=safe_name,
        )

    document = documents_by_filename.get(safe_name)
    if document is None:
        raise _reject(
            error_code="pdf_not_in_corpus",
            http_status=403,
            message=(
                f"O arquivo '{safe_name}' não faz parte do corpus AWS aceito por "
                "esta API."
            ),
            filename=safe_name,
        )

    if document.optional and not api_settings.allow_optional_corpus:
        raise _reject(
            error_code="pdf_optional_disabled",
            http_status=403,
            message=(
                f"O PDF '{safe_name}' é opcional e não está habilitado nesta API."
            ),
            filename=safe_name,
            document_id=document.id,
        )

    try:
        _validate_pdf_content(data)
    except ValueError as exc:
        raise _reject(
            error_code="invalid_pdf",
            http_status=422,
            message=f"O arquivo '{safe_name}' não é um PDF válido.",
            filename=safe_name,
            detail=str(exc),
        ) from exc

    if api_settings.corpus_strict_hash:
        reference_hashes = build_reference_hashes(resolved_manifest, resolved_dir)
        expected = reference_hashes.get(safe_name)
        if expected is None:
            raise _reject(
                error_code="reference_unavailable",
                http_status=503,
                message=(
                    f"Não há referência SHA-256 para '{safe_name}'. "
                    "Preencha sha256 no manifest ou disponibilize o PDF no servidor."
                ),
                filename=safe_name,
                document_id=document.id,
            )

        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise _reject(
                error_code="hash_mismatch",
                http_status=422,
                message=(
                    f"O conteúdo de '{safe_name}' não corresponde ao PDF oficial "
                    "do corpus AWS."
                ),
                filename=safe_name,
                document_id=document.id,
            )

    return document


def corpus_help_payload(
    *,
    error_code: str,
    filename: str | None = None,
    document_id: str | None = None,
    detail: str | None = None,
) -> dict:
    """Build a Portuguese help block for corpus-related errors."""
    allowed_filenames = _allowed_filenames()
    base = {
        "summary": (
            "Esta API processa apenas PDFs oficiais do AWS Well-Architected usados "
            "no treinamento do projeto Orion."
        ),
        "steps": [
            "Consulte GET /api/pdf/help — campo documents lista os arquivos aceitos.",
            "Baixe o PDF oficial no link source_url de cada documento (site da AWS).",
            "Mantenha o nome original do arquivo (ex.: wellarchitected-framework.pdf).",
            (
                "Envie o arquivo com POST /api/pdf (multipart) ou use document_id se "
                "o PDF já estiver no servidor."
            ),
        ],
        "discover": {
            "help": "/api/pdf/help",
            "openapi": "/api/docs",
        },
        "allowed_filenames": allowed_filenames,
    }

    if error_code == "hash_mismatch":
        base["summary"] = (
            "O nome do arquivo está correto, mas o conteúdo é diferente do esperado."
        )
        base["steps"] = [
            (
                "Baixe novamente o PDF oficial em GET /api/pdf/help "
                "→ documents[].source_url."
            ),
            "Não edite, converta ou comprima o arquivo antes do envio.",
            (
                "Se você não tem o PDF local, use: "
                "uv run python -m pipeline.ingestion.cli download-corpus"
            ),
        ]
        if document_id:
            base["expected_document_id"] = document_id

    elif error_code == "pdf_file_not_found":
        base["summary"] = "O PDF oficial ainda não está disponível no servidor."
        base["steps"] = [
            (
                "Baixe o corpus com: "
                "uv run python -m pipeline.ingestion.cli download-corpus"
            ),
            "Ou monte ./pdfs no container pipeline-api.",
            "Consulte GET /api/pdf/help para ver quais arquivos são necessários.",
        ]

    elif error_code == "file_too_large":
        base["summary"] = "O upload excede o tamanho máximo permitido pela API."
        base["steps"] = [
            "Envie apenas o PDF oficial da AWS, sem anexos ou conversões.",
            f"Tamanho máximo: {api_settings.pdf_max_upload_bytes} bytes.",
        ]

    elif error_code == "invalid_pdf":
        base["summary"] = "O arquivo enviado não passou na validação estrutural de PDF."
        base["steps"] = [
            "Confirme que o arquivo é um PDF válido e não está corrompido.",
            "Baixe novamente o PDF oficial em GET /api/pdf/help.",
        ]
        if detail:
            base["detail"] = detail

    elif error_code == "invalid_filename":
        base["summary"] = "O nome do arquivo é inválido ou contém caracteres proibidos."
        base["steps"] = [
            "Use apenas o basename do PDF (sem pastas ou ..).",
            "O filename deve coincidir exatamente com o manifest.",
        ]

    elif error_code == "pdf_optional_disabled":
        base["summary"] = "Este PDF é opcional e não está habilitado nesta instância."
        base["steps"] = [
            "Use um dos PDFs obrigatórios listados em GET /api/pdf/help.",
            "Ou habilite ALLOW_OPTIONAL_CORPUS=true no ambiente da API.",
        ]

    elif error_code == "reference_unavailable":
        base["summary"] = "Não há hash de referência para validar o conteúdo do PDF."
        base["steps"] = [
            (
                "Preencha sha256 no pdfs/manifest.yaml ou disponibilize o PDF "
                "em PDF_DOWNLOAD_DIR."
            ),
            "Execute download-corpus antes de subir a API.",
        ]

    if filename:
        base["filename"] = filename

    return base


def build_pdf_help_response(
    *,
    manifest_path: Path | str | None = None,
    corpus_dir: Path | str | None = None,
) -> dict:
    """Build the GET /api/pdf/help payload."""
    resolved_manifest = Path(manifest_path or settings.pdf_manifest_path).resolve()
    resolved_dir = Path(corpus_dir or settings.pdf_download_dir).resolve()
    status = check_corpus(resolved_manifest, resolved_dir)

    available_by_id = {item.document.id: item.valid_pdf for item in status.files}

    documents = []
    for document in status.documents:
        if document.optional and not api_settings.allow_optional_corpus:
            continue
        documents.append(
            {
                "id": document.id,
                "title": document.title,
                "filename": document.filename,
                "required": not document.optional,
                "available": available_by_id.get(document.id, False),
                "source_url": document.url,
                "doc_page": document.doc_page,
                "how_to_obtain": (
                    "Baixe o PDF em source_url e envie com o filename exato."
                    if document.url
                    else (
                        document.notes
                        or "Baixe manualmente e envie com o filename exato."
                    )
                ),
            }
        )

    return {
        "policy": "aws-well-architected-only",
        "summary": (
            "Esta API aceita apenas PDFs oficiais do corpus AWS Well-Architected "
            "(treinamento Orion). Não envie PDFs genéricos."
        ),
        "corpus": "aws-well-architected",
        "message": (
            "Somente os PDFs listados em documents são aceitos em POST /api/pdf."
        ),
        "flow": {
            "step_1": "Leia documents abaixo — filenames, source_url e document_id",
            "step_2": "Baixe o PDF oficial da AWS (source_url)",
            "step_3": "POST /api/pdf — upload ou document_id",
            "step_4": "Resposta imediata: accepted ou rejected",
            "step_5": "GET /api/jobs/{job_id} — acompanhe um job específico",
            "step_6": "GET /api/jobs — liste todos os jobs (filtros type, status)",
        },
        "accepted_modes": [
            {
                "mode": "upload",
                "content_type": "multipart/form-data",
                "description": "Envie o PDF com o filename exato do manifest.",
            },
            {
                "mode": "document_id",
                "content_type": "application/json",
                "description": "Dispara job para PDF já no servidor (App Geração).",
            },
        ],
        "requirements": [
            "Filename deve estar em pdfs/manifest.yaml",
            "Conteúdo deve ser o PDF oficial AWS (SHA-256)",
            "PDFs fora do corpus são rejeitados antes da fila",
        ],
        "documents": documents,
        "usage": {
            "submit": "POST /api/pdf",
            "monitor_one": "GET /api/jobs/{job_id}",
            "monitor_list": "GET /api/jobs",
        },
        "examples": {
            "help": "curl -s http://localhost:8000/api/pdf/help | jq .",
            "upload": (
                "curl -s -X POST http://localhost:8000/api/pdf "
                "-F file=@wellarchitected-framework.pdf | jq ."
            ),
            "by_id": (
                "curl -s -X POST http://localhost:8000/api/pdf "
                "-H 'Content-Type: application/json' "
                '-d \'{"document_id":"wellarchitected-framework"}\' | jq .'
            ),
            "poll": "curl -s http://localhost:8000/api/jobs/<job_id> | jq .",
            "list_jobs": (
                "curl -s 'http://localhost:8000/api/jobs?type=pdf&limit=20' | jq ."
            ),
        },
        "links": {
            "jobs": "/api/jobs",
            "openapi": "/api/docs",
        },
    }


def _sanitize_filename(filename: str) -> str | None:
    if not filename or not filename.strip():
        return None

    basename = os.path.basename(filename.strip())
    if not basename or basename in {".", ".."}:
        return None
    if UNSAFE_FILENAME.search(filename) or UNSAFE_FILENAME.search(basename):
        return None
    return basename


def _validate_pdf_content(data: bytes) -> None:
    validate_pdf_bytes(data)
    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.is_encrypted and document.needs_pass:
                msg = "PDF is password-protected"
                raise ValueError(msg)
            if document.page_count < 1:
                msg = "PDF has no pages"
                raise ValueError(msg)
            document.load_page(0)
    except fitz.FileDataError as exc:
        msg = "Unable to read PDF (corrupt or invalid)"
        raise ValueError(msg) from exc


def _allowed_filenames() -> list[str]:
    documents = load_manifest(Path(settings.pdf_manifest_path).resolve())
    return [
        doc.filename
        for doc in documents
        if not doc.optional or api_settings.allow_optional_corpus
    ]


def _reject(
    *,
    error_code: str,
    http_status: int,
    message: str,
    filename: str | None,
    document_id: str | None = None,
    detail: str | None = None,
) -> CorpusRejectedError:
    return CorpusRejectedError(
        error_code=error_code,
        http_status=http_status,
        message=message,
        help=corpus_help_payload(
            error_code=error_code,
            filename=filename,
            document_id=document_id,
            detail=detail,
        ),
    )
