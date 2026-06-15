from datetime import UTC, datetime
from pathlib import Path

import fitz
import pytest

from pipeline.ingestion.pdf_reader import read_pdf_metadata, validate_pdf
from pipeline.shared.schemas.pdf_document import PdfDocument


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Minimal PDF with one page of native text."""
    pdf_path = tmp_path / "sample.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Hello PDF corpus")
    document.save(pdf_path)
    document.close()
    return pdf_path


def test_validate_pdf_accepts_valid_pdf(sample_pdf: Path) -> None:
    validate_pdf(sample_pdf)


def test_validate_pdf_rejects_non_pdf(tmp_path: Path) -> None:
    text_file = tmp_path / "not-a-pdf.txt"
    text_file.write_text("plain text", encoding="utf-8")

    with pytest.raises(ValueError, match="Not a PDF file"):
        validate_pdf(text_file)


def test_validate_pdf_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="File not found"):
        validate_pdf(tmp_path / "missing.pdf")


def test_read_pdf_metadata_returns_page_count_and_fields(sample_pdf: Path) -> None:
    doc = read_pdf_metadata(sample_pdf)

    assert doc.page_count == 1
    assert doc.file_name == "sample.pdf"
    assert doc.source_format == "pdf"
    assert doc.title == "sample"
    assert Path(doc.source_path) == sample_pdf.resolve()


def test_pdf_document_to_markdown_includes_source_format() -> None:
    doc = PdfDocument(
        source_path="/tmp/wellarchitected-framework.pdf",
        file_name="wellarchitected-framework.pdf",
        title="wellarchitected-framework",
        page_count=42,
        ingested_at=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
    )

    markdown = doc.to_markdown()

    assert "source_format: pdf" in markdown
    assert "page_count: 42" in markdown
    assert "extração na transformação" in markdown.lower()
