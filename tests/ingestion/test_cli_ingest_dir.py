from pathlib import Path
from unittest.mock import Mock, patch

from pipeline.ingestion.cli import main


@patch("pipeline.ingestion.cli.ingest_directory")
def test_cli_ingest_dir_passes_extensions(mock_ingest: Mock) -> None:
    mock_ingest.return_value = Mock(
        total_files=1,
        succeeded=1,
        failed=0,
        errors=[],
    )

    exit_code = main(["ingest-dir", "--dir", "./pdfs", "--extensions", ".pdf"])

    assert exit_code == 0
    mock_ingest.assert_called_once_with(Path("./pdfs"), [".pdf"])


@patch("pipeline.ingestion.cli.ingest_directory")
def test_cli_ingest_dir_prints_hint_when_no_files_match(
    mock_ingest: Mock,
    tmp_path: Path,
    capsys,
) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "doc.pdf").write_bytes(b"%PDF")

    mock_ingest.return_value = Mock(
        total_files=0,
        succeeded=0,
        failed=0,
        errors=[],
    )

    main(["ingest-dir", "--dir", str(pdf_dir), "--extensions", ".txt"])

    err = capsys.readouterr().err
    assert "No files matched" in err
    assert ".pdf" in err
