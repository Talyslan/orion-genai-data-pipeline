from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from api.config import api_settings
from api.guards.corpus_guard import (
    CorpusRejectedError,
    build_reference_hashes,
    resolve_by_document_id,
    validate_upload,
)


def _write_pdf(path: Path, text: str = "AWS corpus guard") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    path.write_bytes(data)
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def guard_env(tmp_path: Path) -> dict[str, Path]:
    corpus_dir = tmp_path / "pdfs"
    corpus_dir.mkdir()
    pdf_path = corpus_dir / "required.pdf"
    pdf_bytes = _write_pdf(pdf_path)
    pdf_hash = _sha256(pdf_bytes)

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        f"""
corpus: test
documents:
  - id: required-doc
    title: Required Document
    url: https://example.com/required.pdf
    filename: required.pdf
    sha256: "{pdf_hash}"
  - id: optional-doc
    title: Optional Document
    filename: optional.pdf
    optional: true
""".strip(),
        encoding="utf-8",
    )

    return {
        "manifest": manifest,
        "corpus_dir": corpus_dir,
        "pdf_bytes": pdf_bytes,
        "pdf_hash": pdf_hash,
    }


def test_build_reference_hashes_prefers_manifest_sha256(
    guard_env: dict[str, Path],
) -> None:
    hashes = build_reference_hashes(
        guard_env["manifest"],
        guard_env["corpus_dir"],
    )

    assert hashes["required.pdf"] == guard_env["pdf_hash"]


def test_validate_upload_accepts_matching_filename_and_hash(
    guard_env: dict[str, Path],
) -> None:
    document = validate_upload(
        "required.pdf",
        guard_env["pdf_bytes"],
        manifest_path=guard_env["manifest"],
        corpus_dir=guard_env["corpus_dir"],
    )

    assert document.id == "required-doc"
    assert document.filename == "required.pdf"


def test_validate_upload_rejects_unknown_filename(
    guard_env: dict[str, Path],
) -> None:
    with pytest.raises(CorpusRejectedError) as exc_info:
        validate_upload(
            "relatorio.pdf",
            guard_env["pdf_bytes"],
            manifest_path=guard_env["manifest"],
            corpus_dir=guard_env["corpus_dir"],
        )

    error = exc_info.value
    assert error.http_status == 403
    assert error.error_code == "pdf_not_in_corpus"
    assert "steps" in error.help


def test_validate_upload_rejects_hash_mismatch(
    guard_env: dict[str, Path],
) -> None:
    other_bytes = _write_pdf(guard_env["corpus_dir"] / "other.pdf", text="other")

    with pytest.raises(CorpusRejectedError) as exc_info:
        validate_upload(
            "required.pdf",
            other_bytes,
            manifest_path=guard_env["manifest"],
            corpus_dir=guard_env["corpus_dir"],
        )

    error = exc_info.value
    assert error.http_status == 422
    assert error.error_code == "hash_mismatch"
    assert error.help["expected_document_id"] == "required-doc"


def test_validate_upload_rejects_path_traversal(
    guard_env: dict[str, Path],
) -> None:
    with pytest.raises(CorpusRejectedError) as exc_info:
        validate_upload(
            "../required.pdf",
            guard_env["pdf_bytes"],
            manifest_path=guard_env["manifest"],
            corpus_dir=guard_env["corpus_dir"],
        )

    assert exc_info.value.error_code == "invalid_filename"
    assert exc_info.value.http_status == 403


def test_resolve_by_document_id_returns_document(
    guard_env: dict[str, Path],
) -> None:
    document = resolve_by_document_id(
        "required-doc",
        manifest_path=guard_env["manifest"],
        corpus_dir=guard_env["corpus_dir"],
    )

    assert document.filename == "required.pdf"


def test_resolve_by_document_id_rejects_unknown_id(
    guard_env: dict[str, Path],
) -> None:
    with pytest.raises(CorpusRejectedError) as exc_info:
        resolve_by_document_id(
            "unknown-doc",
            manifest_path=guard_env["manifest"],
            corpus_dir=guard_env["corpus_dir"],
        )

    assert exc_info.value.http_status == 403
    assert exc_info.value.error_code == "pdf_not_in_corpus"


def test_resolve_by_document_id_rejects_missing_file(
    guard_env: dict[str, Path],
) -> None:
    (guard_env["corpus_dir"] / "required.pdf").unlink()

    with pytest.raises(CorpusRejectedError) as exc_info:
        resolve_by_document_id(
            "required-doc",
            manifest_path=guard_env["manifest"],
            corpus_dir=guard_env["corpus_dir"],
        )

    assert exc_info.value.http_status == 404
    assert exc_info.value.error_code == "pdf_file_not_found"


def test_validate_upload_rejects_optional_when_disabled(
    guard_env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    optional_bytes = _write_pdf(guard_env["corpus_dir"] / "optional.pdf")
    monkeypatch.setattr(api_settings, "allow_optional_corpus", False)

    with pytest.raises(CorpusRejectedError) as exc_info:
        validate_upload(
            "optional.pdf",
            optional_bytes,
            manifest_path=guard_env["manifest"],
            corpus_dir=guard_env["corpus_dir"],
        )

    assert exc_info.value.error_code == "pdf_optional_disabled"
