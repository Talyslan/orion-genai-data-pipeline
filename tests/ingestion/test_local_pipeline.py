from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pipeline.ingestion.pipeline import IngestionPipeline, ingest_directory
from pipeline.shared.schemas.ingestion_result import IngestionResult
from pipeline.shared.schemas.local_document import LocalDocument


def _ingestion_result(source_path: str, tmp_output_dir: Path) -> IngestionResult:
    return IngestionResult(
        source_path=source_path,
        local_path=tmp_output_dir / "out.md",
        minio_object_key="source/2026/06/08/file.md",
        ingested_at=datetime(2026, 6, 8, 12, 0, tzinfo=UTC),
    )


@pytest.fixture
def local_document(fixtures_dir: Path) -> LocalDocument:
    file_path = fixtures_dir / "sample-prompt.txt"
    return LocalDocument(
        source_path=str(file_path.resolve()),
        file_name="sample-prompt.txt",
        title="sample-prompt",
        content="Conteúdo de teste",
    )


@patch("pipeline.ingestion.pipeline.save_local_document")
@patch("pipeline.ingestion.pipeline.read_local_file")
def test_run_local_ingests_file_and_uploads(
    mock_read: Mock,
    mock_save: Mock,
    local_document: LocalDocument,
    fixtures_dir: Path,
    tmp_output_dir: Path,
) -> None:
    mock_read.return_value = local_document
    local_path = tmp_output_dir / "saved.md"
    mock_save.return_value = local_path

    mock_uploader = Mock()
    mock_uploader.upload_file.return_value = "source/2026/06/08/sample-prompt.md"

    pipeline = IngestionPipeline(
        output_dir=tmp_output_dir,
        uploader=mock_uploader,
    )
    file_path = fixtures_dir / "sample-prompt.txt"
    result = pipeline.run_local(file_path)

    mock_read.assert_called_once_with(file_path)
    mock_save.assert_called_once_with(local_document, tmp_output_dir)
    mock_uploader.upload_file.assert_called_once_with(
        local_path,
        file_stem="sample-prompt",
    )
    assert result.source_path == local_document.source_path
    assert result.local_path == local_path
    assert result.minio_object_key == "source/2026/06/08/sample-prompt.md"
    assert result.url is None


@patch("pipeline.ingestion.pipeline.IngestionPipeline.run_local")
def test_ingest_directory_processes_matching_files(
    mock_run_local: Mock,
    tmp_path: Path,
    tmp_output_dir: Path,
) -> None:
    source_dir = tmp_path / "prompts"
    source_dir.mkdir()
    (source_dir / "a.txt").write_text("A", encoding="utf-8")
    (source_dir / "b.txt").write_text("B", encoding="utf-8")
    (source_dir / "skip.pdf").write_bytes(b"%PDF")

    mock_run_local.side_effect = [
        _ingestion_result(str((source_dir / "a.txt").resolve()), tmp_output_dir),
        _ingestion_result(str((source_dir / "b.txt").resolve()), tmp_output_dir),
    ]

    pipeline = IngestionPipeline(output_dir=tmp_output_dir, uploader=Mock())
    batch = pipeline.ingest_directory(source_dir, extensions=[".txt"])

    assert batch.total_files == 2
    assert batch.succeeded == 2
    assert batch.failed == 0
    assert mock_run_local.call_count == 2


@patch("pipeline.ingestion.pipeline.IngestionPipeline.run_local")
def test_ingest_directory_matches_pdf_extension_case_insensitive(
    mock_run_local: Mock,
    tmp_path: Path,
    tmp_output_dir: Path,
) -> None:
    source_dir = tmp_path / "pdfs"
    source_dir.mkdir()
    pdf_path = source_dir / "doc.PDF"
    pdf_path.write_bytes(b"%PDF-1.4")

    mock_run_local.return_value = _ingestion_result(
        str(pdf_path.resolve()),
        tmp_output_dir,
    )

    pipeline = IngestionPipeline(output_dir=tmp_output_dir, uploader=Mock())
    batch = pipeline.ingest_directory(source_dir, extensions=[".pdf"])

    assert batch.total_files == 1
    mock_run_local.assert_called_once_with(pdf_path)


@patch("pipeline.ingestion.pipeline.IngestionPipeline.run_local")
def test_ingest_directory_continues_on_individual_failure(
    mock_run_local: Mock,
    tmp_path: Path,
    tmp_output_dir: Path,
) -> None:
    source_dir = tmp_path / "prompts"
    source_dir.mkdir()
    file_a = source_dir / "a.txt"
    file_b = source_dir / "b.txt"
    file_a.write_text("A", encoding="utf-8")
    file_b.write_text("B", encoding="utf-8")

    mock_run_local.side_effect = [
        _ingestion_result(str(file_a.resolve()), tmp_output_dir),
        RuntimeError("upload failed"),
    ]

    pipeline = IngestionPipeline(output_dir=tmp_output_dir, uploader=Mock())
    batch = pipeline.ingest_directory(source_dir, extensions=[".txt"])

    assert batch.total_files == 2
    assert batch.succeeded == 1
    assert batch.failed == 1
    assert len(batch.errors) == 1


def test_ingest_directory_raises_for_missing_dir(tmp_output_dir: Path) -> None:
    pipeline = IngestionPipeline(output_dir=tmp_output_dir, uploader=Mock())

    with pytest.raises(FileNotFoundError, match="Source directory not found"):
        pipeline.ingest_directory("/nonexistent/dir")


@patch("pipeline.ingestion.pipeline.IngestionPipeline")
def test_ingest_directory_module_delegates(mock_pipeline_cls: Mock) -> None:
    mock_instance = Mock()
    mock_pipeline_cls.return_value = mock_instance

    ingest_directory("./prompts", [".txt"])

    mock_pipeline_cls.assert_called_once_with()
    mock_instance.ingest_directory.assert_called_once_with("./prompts", [".txt"])
