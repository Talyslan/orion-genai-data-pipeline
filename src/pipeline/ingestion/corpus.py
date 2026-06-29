"""AWS PDF corpus manifest and local file verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from pipeline.ingestion.pdf_reader import validate_pdf


@dataclass(frozen=True)
class CorpusDocument:
    id: str
    title: str
    filename: str
    url: str | None = None
    doc_page: str | None = None
    optional: bool = False
    notes: str | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class CorpusFileStatus:
    document: CorpusDocument
    path: Path
    present: bool
    valid_pdf: bool
    error: str | None = None


@dataclass(frozen=True)
class CorpusStatus:
    corpus_dir: Path
    manifest_path: Path
    documents: tuple[CorpusDocument, ...]
    files: tuple[CorpusFileStatus, ...]

    @property
    def required_documents(self) -> tuple[CorpusDocument, ...]:
        return tuple(doc for doc in self.documents if not doc.optional)

    @property
    def present_count(self) -> int:
        return sum(1 for item in self.files if item.present)

    @property
    def valid_count(self) -> int:
        return sum(1 for item in self.files if item.valid_pdf)

    @property
    def missing_required(self) -> tuple[CorpusFileStatus, ...]:
        return tuple(
            item
            for item in self.files
            if not item.document.optional and not item.valid_pdf
        )

    @property
    def is_ready(self) -> bool:
        return len(self.missing_required) == 0


def _normalize_sha256(value: object) -> str | None:
    if not value:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def load_manifest(manifest_path: Path) -> tuple[CorpusDocument, ...]:
    """Load corpus documents from manifest YAML."""
    resolved = manifest_path.resolve()
    if not resolved.is_file():
        msg = f"Corpus manifest not found: {resolved}"
        raise FileNotFoundError(msg)

    with resolved.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        msg = f"Invalid manifest format (expected mapping): {resolved}"
        raise ValueError(msg)

    raw_documents = data.get("documents")
    if not isinstance(raw_documents, list):
        msg = f"Invalid manifest: missing 'documents' list in {resolved}"
        raise ValueError(msg)

    documents: list[CorpusDocument] = []
    for entry in raw_documents:
        if not isinstance(entry, dict):
            msg = f"Invalid manifest entry in {resolved}: {entry!r}"
            raise ValueError(msg)

        doc_id = entry.get("id")
        title = entry.get("title")
        filename = entry.get("filename")
        if not doc_id or not title or not filename:
            msg = f"Manifest entry missing id/title/filename in {resolved}"
            raise ValueError(msg)

        documents.append(
            CorpusDocument(
                id=str(doc_id),
                title=str(title),
                filename=str(filename),
                url=entry.get("url"),
                doc_page=entry.get("doc_page"),
                optional=bool(entry.get("optional", False)),
                notes=entry.get("notes"),
                sha256=_normalize_sha256(entry.get("sha256")),
            )
        )

    return tuple(documents)


def _inspect_file(document: CorpusDocument, corpus_dir: Path) -> CorpusFileStatus:
    path = (corpus_dir / document.filename).resolve()
    if not path.is_file():
        return CorpusFileStatus(
            document=document,
            path=path,
            present=False,
            valid_pdf=False,
        )

    try:
        validate_pdf(path)
    except Exception as exc:
        return CorpusFileStatus(
            document=document,
            path=path,
            present=True,
            valid_pdf=False,
            error=str(exc),
        )

    return CorpusFileStatus(
        document=document,
        path=path,
        present=True,
        valid_pdf=True,
    )


def check_corpus(
    manifest_path: Path | str | None = None,
    corpus_dir: Path | str | None = None,
) -> CorpusStatus:
    """Verify local PDF files against the corpus manifest."""
    from pipeline.shared.config import settings

    resolved_manifest = Path(manifest_path or settings.pdf_manifest_path).resolve()
    resolved_dir = Path(corpus_dir or settings.pdf_download_dir).resolve()
    documents = load_manifest(resolved_manifest)

    if not resolved_dir.is_dir():
        msg = f"Corpus directory not found: {resolved_dir}"
        raise FileNotFoundError(msg)

    files = tuple(_inspect_file(document, resolved_dir) for document in documents)
    return CorpusStatus(
        corpus_dir=resolved_dir,
        manifest_path=resolved_manifest,
        documents=documents,
        files=files,
    )
