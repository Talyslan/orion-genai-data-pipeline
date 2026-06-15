from pathlib import Path

import fitz
import pytest

from pipeline.ingestion.corpus import check_corpus, load_manifest


def _write_pdf(path: Path, text: str = "AWS corpus") -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
corpus: test
documents:
  - id: required-doc
    title: Required Document
    url: https://example.com/required.pdf
    filename: required.pdf
  - id: optional-doc
    title: Optional Document
    filename: optional.pdf
    optional: true
""".strip(),
        encoding="utf-8",
    )
    return manifest


def test_load_manifest_parses_required_and_optional(
    manifest_path: Path,
) -> None:
    documents = load_manifest(manifest_path)

    assert len(documents) == 2
    assert documents[0].id == "required-doc"
    assert documents[0].optional is False
    assert documents[1].optional is True


def test_check_corpus_reports_missing_required(
    manifest_path: Path,
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "pdfs"
    corpus_dir.mkdir()

    status = check_corpus(manifest_path, corpus_dir)

    assert status.is_ready is False
    assert len(status.missing_required) == 1
    assert status.missing_required[0].document.filename == "required.pdf"


def test_check_corpus_ready_when_required_pdf_valid(
    manifest_path: Path,
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "pdfs"
    corpus_dir.mkdir()
    _write_pdf(corpus_dir / "required.pdf")

    status = check_corpus(manifest_path, corpus_dir)

    assert status.is_ready is True
    assert status.valid_count == 1


def test_check_corpus_raises_for_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Corpus manifest not found"):
        check_corpus(tmp_path / "missing.yaml", tmp_path)


def test_check_corpus_raises_for_missing_directory(
    manifest_path: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="Corpus directory not found"):
        check_corpus(manifest_path, tmp_path / "missing")
