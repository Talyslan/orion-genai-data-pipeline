"""Orchestrate PDF content extraction for the transformation layer."""

from __future__ import annotations

import logging

import fitz

from pipeline.shared.config import settings
from pipeline.shared.schemas.extracted_pdf import ExtractedPdf
from pipeline.transform.pdf_router import route_extraction

logger = logging.getLogger(__name__)

SERVICE = "pdf_extractor"
PDF_MAGIC = b"%PDF"


def _validate_pdf_bytes(body: bytes, *, file_name: str = "") -> None:
    if not body.startswith(PDF_MAGIC):
        label = file_name or "PDF"
        msg = f"Not a PDF file (missing %PDF header): {label}"
        raise ValueError(msg)

    try:
        with fitz.open(stream=body, filetype="pdf") as document:
            if document.is_encrypted and document.needs_pass:
                label = file_name or "PDF"
                msg = f"PDF is password-protected: {label}"
                raise ValueError(msg)
            if document.page_count < 1:
                label = file_name or "PDF"
                msg = f"PDF has no pages: {label}"
                raise ValueError(msg)
    except fitz.FileDataError as exc:
        label = file_name or "PDF"
        msg = f"Unable to read PDF (corrupt or invalid): {label}"
        raise ValueError(msg) from exc


def extract_pdf_content(
    body: bytes,
    *,
    mode: str | None = None,
    max_pages: int | None = None,
    file_name: str = "",
) -> ExtractedPdf:
    """Extract structured Markdown from PDF bytes."""
    _validate_pdf_bytes(body, file_name=file_name)

    resolved_mode = mode or settings.pdf_extraction_mode
    resolved_max_pages = settings.pdf_max_pages if max_pages is None else max_pages

    extracted = route_extraction(
        body,
        mode=resolved_mode,
        max_pages=resolved_max_pages,
        settings=settings,
    )

    if not extracted.markdown.strip():
        logger.warning(
            "PDF produced no extractable text",
            extra={
                "service": SERVICE,
                "file_name": file_name or None,
                "page_count": extracted.page_count,
            },
        )
        msg = f"PDF extraction returned empty content: {file_name or 'PDF'}"
        raise ValueError(msg)

    logger.info(
        "PDF content extracted",
        extra={
            "service": SERVICE,
            "file_name": file_name or None,
            "page_count": extracted.page_count,
            "tables_count": extracted.tables_count,
            "pages_ocr": extracted.pages_ocr,
            "methods_used": extracted.methods_used,
            "char_count": len(extracted.markdown),
        },
    )
    return extracted
