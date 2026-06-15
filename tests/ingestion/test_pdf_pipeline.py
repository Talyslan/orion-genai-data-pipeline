from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import fitz
import pytest

from pipeline.ingestion.pipeline import IngestionPipeline
from pipeline.shared.schemas.pdf_document import PdfDocument


@pytest.fixture
def pdf_document(tmp_path: Path) -> tuple[PdfDocument, Path]:
    pdf_path = tmp_path / "whitepaper.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "AWS Well-Architected")
    document.save(pdf_path)
    document.close()

    doc = PdfDocument(
        source_path=str(pdf_path.resolve()),
        file_name="whitepaper.pdf",
        title="whitepaper",
        page_count=1,
        ingested_at=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
    )
    return doc, pdf_path


@patch("pipeline.ingestion.pipeline.save_pdf_document")
@patch("pipeline.ingestion.pipeline.read_pdf_metadata")
@patch("pipeline.ingestion.pipeline.validate_pdf")
def test_run_local_pdf_uploads_original_to_bronze(
    mock_validate: Mock,
    mock_read_metadata: Mock,
    mock_save_pdf: Mock,
    pdf_document: tuple[PdfDocument, Path],
    tmp_output_dir: Path,
) -> None:
    doc, pdf_path = pdf_document
    mock_read_metadata.return_value = doc
    manifest_path = tmp_output_dir / "manifest.md"
    mock_save_pdf.return_value = manifest_path

    mock_uploader = Mock()
    mock_uploader.upload_file.return_value = "source/2026/06/15/whitepaper.pdf"

    pipeline = IngestionPipeline(output_dir=tmp_output_dir, uploader=mock_uploader)
    result = pipeline.run_local(pdf_path)

    mock_validate.assert_called_once_with(pdf_path)
    mock_read_metadata.assert_called_once_with(pdf_path)
    mock_save_pdf.assert_called_once_with(doc, tmp_output_dir)
    mock_uploader.upload_file.assert_called_once_with(
        pdf_path.resolve(),
        content_type="application/pdf",
        file_stem="whitepaper",
        file_extension=".pdf",
    )
    assert result.source_format == "pdf"
    assert result.page_count == 1
    assert result.minio_object_key.endswith(".pdf")
    assert result.local_path == manifest_path


@patch("pipeline.ingestion.pipeline.read_local_file")
def test_run_local_routes_txt_to_text_flow(
    mock_read_local: Mock,
    fixtures_dir: Path,
    tmp_output_dir: Path,
) -> None:
    from pipeline.shared.schemas.local_document import LocalDocument

    file_path = fixtures_dir / "sample-prompt.txt"
    mock_read_local.return_value = LocalDocument(
        source_path=str(file_path.resolve()),
        file_name="sample-prompt.txt",
        title="sample-prompt",
        content="test",
    )

    mock_uploader = Mock()
    mock_uploader.upload_file.return_value = "source/2026/06/08/sample-prompt.md"

    with patch(
        "pipeline.ingestion.pipeline.save_local_document",
        return_value=tmp_output_dir / "saved.md",
    ):
        pipeline = IngestionPipeline(output_dir=tmp_output_dir, uploader=mock_uploader)
        result = pipeline.run_local(file_path)

    mock_read_local.assert_called_once_with(file_path)
    mock_uploader.upload_file.assert_called_once()
    assert result.source_format is None
    assert result.page_count is None
