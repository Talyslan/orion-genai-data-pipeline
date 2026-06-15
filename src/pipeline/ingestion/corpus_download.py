"""Download AWS PDF corpus entries from manifest URLs."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from pipeline.ingestion.corpus import CorpusDocument, load_manifest
from pipeline.ingestion.pdf_reader import PDF_MAGIC, validate_pdf

logger = logging.getLogger(__name__)

SERVICE = "corpus_download"
MIN_PDF_BYTES = 64


@dataclass(frozen=True)
class DownloadItemResult:
    document: CorpusDocument
    status: str
    path: Path | None = None
    error: str | None = None


@dataclass(frozen=True)
class DownloadBatchResult:
    manifest_path: Path
    corpus_dir: Path
    results: tuple[DownloadItemResult, ...]

    @property
    def downloaded(self) -> int:
        return sum(1 for item in self.results if item.status == "downloaded")

    @property
    def skipped(self) -> int:
        return sum(1 for item in self.results if item.status == "skipped")

    @property
    def failed(self) -> int:
        return sum(1 for item in self.results if item.status == "failed")

    @property
    def no_url(self) -> int:
        return sum(1 for item in self.results if item.status == "no_url")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_pdf_bytes(data: bytes) -> None:
    if not data.startswith(PDF_MAGIC):
        msg = "Not a PDF file (missing %PDF header)"
        raise ValueError(msg)
    if len(data) < MIN_PDF_BYTES:
        msg = f"PDF too small ({len(data)} bytes)"
        raise ValueError(msg)


def download_document(
    document: CorpusDocument,
    corpus_dir: Path,
    *,
    skip_existing: bool,
    timeout: int,
) -> DownloadItemResult:
    if not document.url:
        return DownloadItemResult(
            document=document,
            status="no_url",
            error="No URL in manifest (manual download required)",
        )

    dest = corpus_dir / document.filename

    try:
        response = requests.get(document.url, timeout=timeout)
        response.raise_for_status()
        data = response.content
        validate_pdf_bytes(data)
        remote_hash = hashlib.sha256(data).hexdigest()

        if skip_existing and dest.is_file():
            if file_sha256(dest) == remote_hash:
                logger.info(
                    "Skipped unchanged PDF",
                    extra={
                        "service": SERVICE,
                        "pdf_filename": document.filename,
                        "status": "skipped",
                    },
                )
                return DownloadItemResult(
                    document=document, status="skipped", path=dest
                )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        validate_pdf(dest)

        logger.info(
            "Downloaded PDF",
            extra={
                "service": SERVICE,
                "pdf_filename": document.filename,
                "status": "downloaded",
                "bytes": len(data),
            },
        )
        return DownloadItemResult(document=document, status="downloaded", path=dest)
    except Exception as exc:
        logger.error(
            "PDF download failed",
            extra={
                "service": SERVICE,
                "pdf_filename": document.filename,
                "url": document.url,
                "error": str(exc),
            },
        )
        return DownloadItemResult(
            document=document,
            status="failed",
            path=dest if dest.is_file() else None,
            error=str(exc),
        )


def download_corpus(
    manifest_path: Path | str | None = None,
    corpus_dir: Path | str | None = None,
    *,
    skip_existing: bool | None = None,
    timeout: int | None = None,
) -> DownloadBatchResult:
    """Download all manifest entries with URLs into the corpus directory."""
    from pipeline.shared.config import settings

    resolved_manifest = Path(manifest_path or settings.pdf_manifest_path).resolve()
    resolved_dir = Path(corpus_dir or settings.pdf_download_dir).resolve()
    documents = load_manifest(resolved_manifest)
    effective_skip = (
        settings.pdf_download_skip_existing if skip_existing is None else skip_existing
    )
    effective_timeout = timeout or settings.pdf_download_timeout_seconds

    resolved_dir.mkdir(parents=True, exist_ok=True)
    results = tuple(
        download_document(
            document,
            resolved_dir,
            skip_existing=effective_skip,
            timeout=effective_timeout,
        )
        for document in documents
    )

    return DownloadBatchResult(
        manifest_path=resolved_manifest,
        corpus_dir=resolved_dir,
        results=results,
    )
