from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.jobs.store import JobStore


def _write_pdf(path: Path, text: str = "pdf route test") -> bytes:
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
def pdf_route_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    corpus_dir = tmp_path / "pdfs"
    corpus_dir.mkdir()
    pdf_bytes = _write_pdf(corpus_dir / "required.pdf")
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
""".strip(),
        encoding="utf-8",
    )

    store = JobStore(ttl_seconds=3600)
    enqueued: list[str] = []

    from pipeline.shared.config.settings import settings

    monkeypatch.setattr(settings, "pdf_manifest_path", str(manifest))
    monkeypatch.setattr(settings, "pdf_download_dir", str(corpus_dir))
    monkeypatch.setattr("api.routes.pdf.get_job_store", lambda: store)
    monkeypatch.setattr(
        "api.routes.pdf.enqueue_job",
        lambda job_id: enqueued.append(job_id),
    )

    return {
        "store": store,
        "enqueued": enqueued,
        "pdf_bytes": pdf_bytes,
        "pdf_hash": pdf_hash,
    }


def test_pdf_help_returns_documents(pdf_route_env: dict[str, object]) -> None:
    response = TestClient(app).get("/api/pdf/help")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy"] == "aws-well-architected-only"
    assert len(payload["documents"]) == 1
    assert payload["documents"][0]["id"] == "required-doc"


def test_post_pdf_document_id_accepted(pdf_route_env: dict[str, object]) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/pdf",
        json={"document_id": "required-doc"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["enqueued"] is True
    assert payload["type"] == "pdf"
    assert payload["poll"] == f"/api/jobs/{payload['job_id']}"
    assert payload["input"]["mode"] == "document_id"
    assert response.headers["X-Corpus-Policy"] == "aws-well-architected-only"
    assert response.headers["X-Corpus-Catalog"] == "/api/pdf/help"
    assert pdf_route_env["enqueued"] == [payload["job_id"]]


def test_post_pdf_upload_accepted(pdf_route_env: dict[str, object]) -> None:
    pdf_bytes = pdf_route_env["pdf_bytes"]
    client = TestClient(app)
    response = client.post(
        "/api/pdf",
        files={"file": ("required.pdf", BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["enqueued"] is True
    assert payload["input"]["mode"] == "upload"
    assert payload["input"]["filename"] == "required.pdf"


def test_post_pdf_rejects_unknown_filename(pdf_route_env: dict[str, object]) -> None:
    pdf_bytes = pdf_route_env["pdf_bytes"]
    client = TestClient(app)
    response = client.post(
        "/api/pdf",
        files={"file": ("relatorio.pdf", BytesIO(pdf_bytes), "application/pdf")},
    )

    assert response.status_code == 403
    payload = response.json()
    assert payload["enqueued"] is False
    assert payload["error"] == "pdf_not_in_corpus"
    assert "steps" in payload["help"]
    assert pdf_route_env["enqueued"] == []


def test_post_pdf_rejects_unknown_document_id(
    pdf_route_env: dict[str, object],
) -> None:
    response = TestClient(app).post(
        "/api/pdf",
        json={"document_id": "unknown-doc"},
    )

    assert response.status_code == 403
    assert response.json()["enqueued"] is False


def test_post_pdf_rejects_invalid_content_type() -> None:
    response = TestClient(app).post(
        "/api/pdf",
        content=b"plain text",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 422
    assert response.json()["enqueued"] is False
