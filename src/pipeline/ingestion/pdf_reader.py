"""PDF validation and metadata extraction for ingestion."""

import logging
from datetime import UTC, datetime
from pathlib import Path

import fitz

from pipeline.shared.schemas.pdf_document import PdfDocument

logger = logging.getLogger(__name__)

SERVICE = "pdf_reader"
PDF_MAGIC = b"%PDF"


def validate_pdf(file_path: Path) -> None:
    """Raise ValueError if the file is not a readable PDF."""
    resolved = file_path.resolve()

    if not resolved.is_file():
        msg = f"File not found: {resolved}"
        raise FileNotFoundError(msg)

    header = resolved.read_bytes()[:4]
    if not header.startswith(PDF_MAGIC):
        msg = f"Not a PDF file (missing %PDF header): {resolved}"
        raise ValueError(msg)

    try:
        with fitz.open(resolved) as document:
            if document.page_count < 1:
                msg = f"PDF has no pages: {resolved}"
                raise ValueError(msg)
    except fitz.FileDataError as exc:
        msg = f"Unable to read PDF: {resolved}"
        raise ValueError(msg) from exc


def read_pdf_metadata(file_path: Path) -> PdfDocument:
    """Read PDF metadata without full text extraction."""
    resolved = file_path.resolve()
    validate_pdf(resolved)

    logger.info(
        "Reading PDF metadata",
        extra={"service": SERVICE, "source_path": str(resolved)},
    )

    try:
        with fitz.open(resolved) as document:
            page_count = document.page_count
            title = resolved.stem
            metadata_title = document.metadata.get("title")
            if metadata_title and metadata_title.strip():
                title = metadata_title.strip()
    except fitz.FileDataError:
        logger.exception(
            "Failed to read PDF metadata",
            extra={"service": SERVICE, "source_path": str(resolved)},
        )
        raise

    doc = PdfDocument(
        source_path=str(resolved),
        file_name=resolved.name,
        title=title,
        page_count=page_count,
        ingested_at=datetime.now(UTC),
    )

    logger.info(
        "PDF metadata read",
        extra={
            "service": SERVICE,
            "source_path": str(resolved),
            "page_count": page_count,
        },
    )

    return doc
