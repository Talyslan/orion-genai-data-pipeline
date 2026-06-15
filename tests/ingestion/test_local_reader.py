from pathlib import Path

import pytest

from pipeline.ingestion.local_reader import read_local_file


def test_read_local_file_reads_content_and_metadata(
    fixtures_dir: Path,
) -> None:
    file_path = fixtures_dir / "sample-prompt.txt"

    doc = read_local_file(file_path)

    assert doc.source_path == str(file_path.resolve())
    assert doc.file_name == "sample-prompt.txt"
    assert doc.title == "sample-prompt"
    assert "assistente útil" in doc.content
    assert doc.ingested_at is not None


def test_read_local_file_raises_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError, match="File not found"):
        read_local_file(missing)


def test_read_local_file_rejects_pdf_files(tmp_path: Path) -> None:
    pdf_file = tmp_path / "document.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\ncontent")

    with pytest.raises(ValueError, match="PDF files must use the PDF ingestion path"):
        read_local_file(pdf_file)


def test_read_local_file_handles_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    doc = read_local_file(empty_file)

    assert doc.content == ""
    assert doc.title == "empty"
