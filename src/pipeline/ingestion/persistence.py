"""Local file persistence for scraped and local content."""

import logging
import uuid
from pathlib import Path

from pipeline.shared.schemas.local_document import LocalDocument
from pipeline.shared.schemas.pdf_document import PdfDocument
from pipeline.shared.schemas.scraped_page import ScrapedPage

logger = logging.getLogger(__name__)


def save_local_document(doc: LocalDocument, output_dir: Path) -> Path:
    """Save a local document as Markdown and return the absolute file path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / f"{uuid.uuid4()}.md"
    file_path.write_text(doc.to_markdown(), encoding="utf-8")

    absolute_path = file_path.resolve()
    logger.info("Local document saved to %s", absolute_path)

    return absolute_path


def save_pdf_document(doc: PdfDocument, output_dir: Path) -> Path:
    """Save PDF ingestion metadata as Markdown and return the absolute file path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / f"{uuid.uuid4()}.md"
    file_path.write_text(doc.to_markdown(), encoding="utf-8")

    absolute_path = file_path.resolve()
    logger.info("PDF metadata saved to %s", absolute_path)

    return absolute_path


def save_scraped_page(page: ScrapedPage, output_dir: Path) -> Path:
    """Save a scraped page as Markdown and return the absolute file path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / f"{uuid.uuid4()}.md"
    file_path.write_text(page.to_markdown(), encoding="utf-8")

    absolute_path = file_path.resolve()
    logger.info("Scraped page saved to %s", absolute_path)

    return absolute_path
