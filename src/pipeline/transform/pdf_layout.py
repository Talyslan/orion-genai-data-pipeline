"""Structured PDF layout extraction — tables, blocks and figure placeholders."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import fitz
import pdfplumber

from pipeline.transform.pdf_ocr import resolve_page_text

if TYPE_CHECKING:
    from pipeline.shared.config.settings import Settings

logger = logging.getLogger(__name__)

SERVICE = "pdf_layout"


@dataclass(frozen=True)
class PageExtraction:
    text: str
    tables_count: int = 0
    figures_count: int = 0
    method: str = "native"


def table_to_markdown(table: list[list[str | None]]) -> str:
    """Convert a pdfplumber table to a Markdown pipe table."""
    if not table:
        return ""

    rows: list[list[str]] = []
    for row in table:
        cells = [(cell or "").strip().replace("\n", " ") for cell in row]
        if any(cells):
            rows.append(cells)

    if not rows:
        return ""

    col_count = max(len(row) for row in rows)
    normalized = [row + [""] * (col_count - len(row)) for row in rows]
    header = normalized[0]
    separator = ["---"] * col_count
    body = normalized[1:] if len(normalized) > 1 else []

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def figure_placeholder(page_number: int, figure_index: int) -> str:
    """Return a textual placeholder for a non-text figure block."""
    return (
        f"![figure page {page_number} #{figure_index}]"
        f"(diagram — conteúdo visual sem texto extraído)"
    )


def _ordered_text_blocks(page: fitz.Page) -> str:
    """Extract text blocks sorted top-to-bottom, left-to-right."""
    blocks = page.get_text("blocks")
    text_blocks = [
        block
        for block in blocks
        if len(block) >= 5 and block[6] == 0 and str(block[4]).strip()
    ]
    text_blocks.sort(key=lambda block: (round(block[1], 1), round(block[0], 1)))
    return "\n\n".join(str(block[4]).strip() for block in text_blocks)


def _figure_count(page: fitz.Page) -> int:
    return len(page.get_images(full=True))


def extract_native_page(page: fitz.Page, settings: Settings) -> PageExtraction:
    """Extract linear native text from a page with optional OCR fallback."""
    native_text = page.get_text("text")
    text, method = resolve_page_text(
        page,
        native_text,
        ocr_enabled=settings.pdf_ocr_enabled,
        min_chars=settings.pdf_ocr_min_chars,
        dpi=settings.pdf_ocr_dpi,
        lang=settings.pdf_ocr_lang,
    )
    return PageExtraction(text=text, method=method)


def extract_structured_page(
    plumber_page: pdfplumber.page.Page,
    fitz_page: fitz.Page,
    settings: Settings,
) -> PageExtraction:
    """Extract tables, ordered blocks, OCR fallback and figure placeholders."""
    parts: list[str] = []
    tables_count = 0
    figures_count = 0

    if settings.pdf_extract_tables:
        for table in plumber_page.extract_tables() or []:
            markdown = table_to_markdown(table)
            if markdown:
                parts.append(markdown)
                tables_count += 1

    block_text = _ordered_text_blocks(fitz_page)
    if block_text.strip():
        parts.append(block_text.strip())

    figures_count = _figure_count(fitz_page)
    if settings.pdf_figure_placeholder and figures_count:
        for index in range(1, figures_count + 1):
            parts.append(figure_placeholder(fitz_page.number + 1, index))

    combined = "\n\n".join(part for part in parts if part.strip())
    text, method = resolve_page_text(
        fitz_page,
        combined,
        ocr_enabled=settings.pdf_ocr_enabled,
        min_chars=settings.pdf_ocr_min_chars,
        dpi=settings.pdf_ocr_dpi,
        lang=settings.pdf_ocr_lang,
    )

    return PageExtraction(
        text=text,
        tables_count=tables_count,
        figures_count=figures_count,
        method=method,
    )


def open_pdf_streams(body: bytes) -> tuple[fitz.Document, pdfplumber.PDF]:
    """Open the same PDF bytes with PyMuPDF and pdfplumber."""
    fitz_doc = fitz.open(stream=body, filetype="pdf")
    plumber_doc = pdfplumber.open(io.BytesIO(body))
    return fitz_doc, plumber_doc
