"""Route PDF extraction to native, structured or unstructured strategies."""

from __future__ import annotations

import logging

import fitz

from pipeline.shared.config.settings import Settings
from pipeline.shared.schemas.extracted_pdf import ExtractedPdf
from pipeline.transform.pdf_layout import (
    PageExtraction,
    extract_native_page,
    extract_structured_page,
    open_pdf_streams,
)

logger = logging.getLogger(__name__)

SERVICE = "pdf_router"


def _page_limit(document: fitz.Document, max_pages: int) -> int:
    total = document.page_count
    if max_pages > 0:
        return min(total, max_pages)
    return total


def _aggregate_pages(
    page_results: list[PageExtraction],
    *,
    page_count: int,
    methods_used: set[str],
) -> ExtractedPdf:
    markdown = "\n\n".join(
        result.text for result in page_results if result.text.strip()
    )
    return ExtractedPdf(
        markdown=markdown,
        page_count=page_count,
        tables_count=sum(result.tables_count for result in page_results),
        figures_count=sum(result.figures_count for result in page_results),
        pages_native=sum(1 for result in page_results if result.method == "native"),
        pages_ocr=sum(1 for result in page_results if result.method == "ocr"),
        methods_used=sorted(methods_used),
    )


def extract_native(body: bytes, settings: Settings, max_pages: int) -> ExtractedPdf:
    """Extract PDF content using PyMuPDF linear text."""
    methods_used: set[str] = {"native"}
    page_results: list[PageExtraction] = []

    with fitz.open(stream=body, filetype="pdf") as document:
        limit = _page_limit(document, max_pages)
        for page_index in range(limit):
            page = document.load_page(page_index)
            result = extract_native_page(page, settings)
            page_results.append(result)
            if result.method == "ocr":
                methods_used.add("ocr")

    return _aggregate_pages(
        page_results,
        page_count=limit,
        methods_used=methods_used,
    )


def extract_structured(body: bytes, settings: Settings, max_pages: int) -> ExtractedPdf:
    """Extract PDF content with pdfplumber tables and ordered blocks."""
    methods_used: set[str] = {"pdfplumber", "native"}
    page_results: list[PageExtraction] = []

    fitz_doc, plumber_doc = open_pdf_streams(body)
    try:
        limit = _page_limit(fitz_doc, max_pages)
        for page_index in range(limit):
            fitz_page = fitz_doc.load_page(page_index)
            plumber_page = plumber_doc.pages[page_index]
            result = extract_structured_page(plumber_page, fitz_page, settings)
            page_results.append(result)
            if result.method == "ocr":
                methods_used.add("ocr")
    finally:
        plumber_doc.close()
        fitz_doc.close()

    return _aggregate_pages(
        page_results,
        page_count=limit,
        methods_used=methods_used,
    )


def extract_unstructured(
    body: bytes,
    settings: Settings,
    max_pages: int,
) -> ExtractedPdf:
    """Extract PDF via unstructured when installed; fallback to structured."""
    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError:
        logger.warning(
            "unstructured not installed; falling back to structured extraction",
            extra={"service": SERVICE},
        )
        return extract_structured(body, settings, max_pages)

    methods_used: set[str] = {"unstructured"}
    with fitz.open(stream=body, filetype="pdf") as document:
        limit = _page_limit(document, max_pages)

    temp_path = None
    try:
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(body)
            temp_path = Path(handle.name)

        elements = partition_pdf(filename=str(temp_path))
        if max_pages > 0:
            elements = [
                element
                for element in elements
                if getattr(element.metadata, "page_number", 1) <= max_pages
            ]

        markdown = "\n\n".join(
            element.text.strip()
            for element in elements
            if getattr(element, "text", None) and element.text.strip()
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return ExtractedPdf(
        markdown=markdown,
        page_count=limit,
        methods_used=sorted(methods_used),
    )


def route_extraction(
    body: bytes,
    *,
    mode: str,
    max_pages: int,
    settings: Settings | None = None,
) -> ExtractedPdf:
    """Select and run the configured PDF extraction strategy."""
    from pipeline.shared.config import settings as default_settings

    resolved_settings = settings or default_settings
    normalized_mode = mode.strip().lower()

    if normalized_mode == "native":
        return extract_native(body, resolved_settings, max_pages)
    if normalized_mode == "structured":
        return extract_structured(body, resolved_settings, max_pages)
    if normalized_mode == "unstructured":
        return extract_unstructured(body, resolved_settings, max_pages)

    msg = f"Unsupported PDF extraction mode: {mode}"
    raise ValueError(msg)
