from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from api.catalog import (
    build_pdf_help_documents,
    build_site_help_entries,
    load_sites_manifest,
)


def _write_pdf(path: Path, text: str = "catalog test") -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


@pytest.fixture
def catalog_env(tmp_path: Path) -> dict[str, Path]:
    corpus_dir = tmp_path / "pdfs"
    corpus_dir.mkdir()
    _write_pdf(corpus_dir / "required.pdf")

    pdf_manifest = tmp_path / "pdf-manifest.yaml"
    pdf_manifest.write_text(
        """
corpus: test
documents:
  - id: required-doc
    title: Required Document
    url: https://example.com/required.pdf
    filename: required.pdf
    doc_page: https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html
  - id: optional-doc
    title: Optional Document
    filename: optional.pdf
    optional: true
    doc_page: https://docs.aws.amazon.com/whitepapers/latest/serverless-architectures-lambda/welcome.html
""".strip(),
        encoding="utf-8",
    )

    sites_manifest = tmp_path / "sites-manifest.yaml"
    sites_manifest.write_text(
        """
corpus: test-sites
sites:
  - id: aws-overview
    title: AWS Overview
    url: https://docs.aws.amazon.com/whitepapers/latest/aws-overview/aws-overview.html
    related_pdf: null
    optional: false
""".strip(),
        encoding="utf-8",
    )

    return {
        "pdf_manifest": pdf_manifest,
        "corpus_dir": corpus_dir,
        "sites_manifest": sites_manifest,
    }


def test_build_pdf_help_documents_marks_available_pdf(
    catalog_env: dict[str, Path],
) -> None:
    documents = build_pdf_help_documents(
        manifest_path=catalog_env["pdf_manifest"],
        corpus_dir=catalog_env["corpus_dir"],
    )

    assert len(documents) == 1
    assert documents[0]["id"] == "required-doc"
    assert documents[0]["available"] is True
    assert documents[0]["doc_page"].startswith("https://docs.aws.amazon.com/")


def test_build_site_help_entries_merges_pdf_and_sites_manifests(
    catalog_env: dict[str, Path],
) -> None:
    sites = build_site_help_entries(
        pdf_manifest_path=catalog_env["pdf_manifest"],
        sites_manifest_path=catalog_env["sites_manifest"],
    )

    assert len(sites) == 2
    assert sites[0]["source"] == "pdf_manifest"
    assert sites[0]["id"] == "required-doc-page"
    assert sites[0]["related_pdf"] == "required-doc"
    assert sites[1]["source"] == "sites_manifest"
    assert sites[1]["id"] == "aws-overview"


def test_build_site_help_entries_deduplicates_urls(
    catalog_env: dict[str, Path],
) -> None:
    catalog_env["sites_manifest"].write_text(
        """
corpus: test-sites
sites:
  - id: duplicate-page
    title: Duplicate
    url: https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html
    optional: false
""".strip(),
        encoding="utf-8",
    )

    sites = build_site_help_entries(
        pdf_manifest_path=catalog_env["pdf_manifest"],
        sites_manifest_path=catalog_env["sites_manifest"],
    )

    assert len(sites) == 1
    assert sites[0]["source"] == "pdf_manifest"


def test_load_sites_manifest_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_sites_manifest(tmp_path / "missing.yaml") == ()
