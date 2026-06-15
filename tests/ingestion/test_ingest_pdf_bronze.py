from pathlib import Path
from unittest.mock import Mock

import fitz

from pipeline.bronze.uploader import BronzeUploader
from pipeline.ingestion.pipeline import IngestionPipeline


def _write_pdf(path: Path, text: str = "AWS Well-Architected corpus") -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_ingest_pdf_fixture_uploads_original_binary_to_bronze(
    tmp_path: Path,
    tmp_output_dir: Path,
) -> None:
    pdf_path = tmp_path / "wellarchitected-framework.pdf"
    _write_pdf(pdf_path)

    mock_client = Mock()
    mock_client.bucket_exists.return_value = True
    uploader = BronzeUploader(client=mock_client)
    pipeline = IngestionPipeline(output_dir=tmp_output_dir, uploader=uploader)

    result = pipeline.run_local(pdf_path)

    assert result.source_format == "pdf"
    assert result.page_count == 1
    assert result.minio_object_key.endswith("wellarchitected-framework.pdf")
    assert result.local_path.suffix == ".md"
    assert result.local_path.exists()

    mock_client.fput_object.assert_called_once()
    call = mock_client.fput_object.call_args
    assert call.args[2] == str(pdf_path.resolve())
    assert call.kwargs["content_type"] == "application/pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_ingest_directory_records_invalid_pdf_without_aborting_batch(
    tmp_path: Path,
    tmp_output_dir: Path,
) -> None:
    source_dir = tmp_path / "pdfs"
    source_dir.mkdir()
    valid_pdf = source_dir / "good.pdf"
    invalid_pdf = source_dir / "bad.pdf"
    _write_pdf(valid_pdf)
    invalid_pdf.write_bytes(b"%PDF-1.4\nbroken")

    mock_client = Mock()
    mock_client.bucket_exists.return_value = True
    uploader = BronzeUploader(client=mock_client)
    pipeline = IngestionPipeline(output_dir=tmp_output_dir, uploader=uploader)

    batch = pipeline.ingest_directory(source_dir, extensions=[".pdf"])

    assert batch.total_files == 2
    assert batch.succeeded == 1
    assert batch.failed == 1
    assert batch.results[0].minio_object_key.endswith("good.pdf")
    assert "Unable to read PDF" in batch.errors[0].error
