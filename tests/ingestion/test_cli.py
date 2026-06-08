from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from pipeline.ingestion.cli import main
from pipeline.shared.schemas.ingestion_result import IngestionResult


@patch("pipeline.ingestion.cli.run_local_ingestion")
def test_cli_ingest_file_success(
    mock_run: Mock,
    fixtures_dir: Path,
    tmp_path: Path,
    capsys,
) -> None:
    file_path = fixtures_dir / "sample-prompt.txt"
    mock_run.return_value = IngestionResult(
        source_path=str(file_path.resolve()),
        local_path=tmp_path / "out.md",
        minio_object_key="source/2026/06/08/sample-prompt.md",
        ingested_at=datetime(2026, 6, 8, 12, 0, tzinfo=UTC),
    )

    exit_code = main(["ingest-file", str(file_path)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Ingestion completed" in output
    assert "sample-prompt" in output


def test_cli_ingest_file_missing_file(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing.txt"

    exit_code = main(["ingest-file", str(missing)])

    assert exit_code == 2
    assert "file not found" in capsys.readouterr().err


@patch("pipeline.ingestion.cli.ingest_directory")
def test_cli_ingest_dir_success(mock_ingest: Mock, capsys) -> None:
    mock_ingest.return_value = Mock(
        total_files=2,
        succeeded=2,
        failed=0,
        errors=[],
    )

    exit_code = main(["ingest-dir", "--dir", "./prompts"])

    assert exit_code == 0
    assert "Batch ingestion completed" in capsys.readouterr().out
