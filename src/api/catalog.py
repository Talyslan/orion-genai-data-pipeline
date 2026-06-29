"""Catalog builders for GET /api/pdf/help and GET /api/site/help."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from api.config import api_settings
from pipeline.ingestion.corpus import check_corpus, load_manifest
from pipeline.shared.config.settings import settings


@dataclass(frozen=True)
class SiteManifestEntry:
    id: str
    title: str
    url: str
    related_pdf: str | None = None
    optional: bool = False


def build_pdf_help_documents(
    *,
    manifest_path: Path | str | None = None,
    corpus_dir: Path | str | None = None,
) -> list[dict]:
    """Build the documents array for GET /api/pdf/help."""
    resolved_manifest = Path(manifest_path or settings.pdf_manifest_path).resolve()
    resolved_dir = Path(corpus_dir or settings.pdf_download_dir).resolve()
    status = check_corpus(resolved_manifest, resolved_dir)

    available_by_id = {item.document.id: item.valid_pdf for item in status.files}

    documents: list[dict] = []
    for document in status.documents:
        if document.optional and not api_settings.allow_optional_corpus:
            continue
        documents.append(
            {
                "id": document.id,
                "title": document.title,
                "filename": document.filename,
                "required": not document.optional,
                "available": available_by_id.get(document.id, False),
                "source_url": document.url,
                "doc_page": document.doc_page,
                "how_to_obtain": (
                    "Baixe o PDF em source_url e envie com o filename exato."
                    if document.url
                    else (
                        document.notes
                        or "Baixe manualmente e envie com o filename exato."
                    )
                ),
            }
        )

    return documents


def load_sites_manifest(
    manifest_path: Path | str | None = None,
) -> tuple[SiteManifestEntry, ...]:
    """Load extra site entries from sites/manifest.yaml."""
    resolved = Path(manifest_path or api_settings.site_manifest_path).resolve()
    if not resolved.is_file():
        return ()

    with resolved.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        msg = f"Invalid sites manifest format (expected mapping): {resolved}"
        raise ValueError(msg)

    raw_sites = data.get("sites")
    if not isinstance(raw_sites, list):
        msg = f"Invalid sites manifest: missing 'sites' list in {resolved}"
        raise ValueError(msg)

    entries: list[SiteManifestEntry] = []
    for entry in raw_sites:
        if not isinstance(entry, dict):
            msg = f"Invalid sites manifest entry in {resolved}: {entry!r}"
            raise ValueError(msg)

        site_id = entry.get("id")
        title = entry.get("title")
        url = entry.get("url")
        if not site_id or not title or not url:
            msg = f"Sites manifest entry missing id/title/url in {resolved}"
            raise ValueError(msg)

        related_pdf = entry.get("related_pdf")
        entries.append(
            SiteManifestEntry(
                id=str(site_id),
                title=str(title),
                url=str(url),
                related_pdf=str(related_pdf) if related_pdf else None,
                optional=bool(entry.get("optional", False)),
            )
        )

    return tuple(entries)


def build_site_help_entries(
    *,
    pdf_manifest_path: Path | str | None = None,
    sites_manifest_path: Path | str | None = None,
) -> list[dict]:
    """Build the sites array for GET /api/site/help."""
    resolved_pdf_manifest = Path(
        pdf_manifest_path or settings.pdf_manifest_path
    ).resolve()
    pdf_documents = load_manifest(resolved_pdf_manifest)
    sites_manifest = load_sites_manifest(sites_manifest_path)

    entries: list[dict] = []
    seen_urls: set[str] = set()

    for document in pdf_documents:
        if not document.doc_page:
            continue
        if document.optional and not api_settings.allow_optional_corpus:
            continue

        url = document.doc_page.strip()
        if url in seen_urls:
            continue

        seen_urls.add(url)
        entries.append(
            {
                "id": f"{document.id}-page",
                "title": document.title,
                "url": url,
                "source": "pdf_manifest",
                "related_pdf": document.id,
                "required": not document.optional,
            }
        )

    for site in sites_manifest:
        if site.optional and not api_settings.allow_optional_corpus:
            continue

        url = site.url.strip()
        if url in seen_urls:
            continue

        seen_urls.add(url)
        entries.append(
            {
                "id": site.id,
                "title": site.title,
                "url": url,
                "source": "sites_manifest",
                "related_pdf": site.related_pdf,
                "required": not site.optional,
            }
        )

    return entries
