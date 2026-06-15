from pathlib import Path
from unittest.mock import Mock, patch

import fitz
import pytest

from pipeline.ingestion.corpus import CorpusDocument, load_manifest
from pipeline.ingestion.corpus_download import (
    download_corpus,
    download_document,
    file_sha256,
    validate_pdf_bytes,
)


def _pdf_bytes(text: str = "AWS whitepaper") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
corpus: test
documents:
  - id: doc-a
    title: Document A
    url: https://example.com/a.pdf
    filename: a.pdf
  - id: doc-b
    title: Document B
    filename: b.pdf
    optional: true
""".strip(),
        encoding="utf-8",
    )
    return manifest


def test_validate_pdf_bytes_rejects_non_pdf() -> None:
    with pytest.raises(ValueError, match="Not a PDF"):
        validate_pdf_bytes(b"not-a-pdf")


def test_download_document_saves_valid_pdf(tmp_path: Path) -> None:
    document = CorpusDocument(
        id="doc-a",
        title="Document A",
        filename="a.pdf",
        url="https://example.com/a.pdf",
    )
    payload = _pdf_bytes()

    with patch(
        "pipeline.ingestion.corpus_download.requests.get",
        return_value=Mock(status_code=200, content=payload, raise_for_status=Mock()),
    ):
        result = download_document(
            document,
            tmp_path,
            skip_existing=True,
            timeout=30,
        )

    assert result.status == "downloaded"
    assert (tmp_path / "a.pdf").is_file()
    validate_pdf_bytes((tmp_path / "a.pdf").read_bytes())


def test_download_document_skips_when_hash_matches(
    tmp_path: Path,
    manifest_path: Path,
) -> None:
    corpus_dir = tmp_path / "pdfs"
    corpus_dir.mkdir()
    payload = _pdf_bytes("same content")
    (corpus_dir / "a.pdf").write_bytes(payload)

    document = load_manifest(manifest_path)[0]

    with patch(
        "pipeline.ingestion.corpus_download.requests.get",
        return_value=Mock(status_code=200, content=payload, raise_for_status=Mock()),
    ):
        result = download_document(
            document,
            corpus_dir,
            skip_existing=True,
            timeout=30,
        )

    assert result.status == "skipped"
    assert file_sha256(corpus_dir / "a.pdf") == file_sha256(corpus_dir / "a.pdf")


def test_download_document_reports_no_url(tmp_path: Path) -> None:
    document = CorpusDocument(
        id="manual",
        title="Manual",
        filename="manual.pdf",
    )

    result = download_document(
        document,
        tmp_path,
        skip_existing=True,
        timeout=30,
    )

    assert result.status == "no_url"


def test_download_corpus_continues_after_network_failure(
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "pdfs"
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
corpus: test
documents:
  - id: doc-a
    title: Document A
    url: https://example.com/a.pdf
    filename: a.pdf
  - id: doc-b
    title: Document B
    url: https://example.com/b.pdf
    filename: b.pdf
""".strip(),
        encoding="utf-8",
    )

    def fake_get(url: str, timeout: int) -> Mock:
        if url.endswith("a.pdf"):
            raise ConnectionError("network down")
        return Mock(
            status_code=200,
            content=_pdf_bytes("ok"),
            raise_for_status=Mock(),
        )

    with patch(
        "pipeline.ingestion.corpus_download.requests.get",
        side_effect=fake_get,
    ):
        batch = download_corpus(manifest, corpus_dir)

    assert batch.failed == 1
    assert batch.downloaded == 1
    assert (corpus_dir / "b.pdf").is_file()
