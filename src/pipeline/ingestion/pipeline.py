"""Orchestration of scrape/local read → local persistence → MinIO Bronze upload."""

import logging
from pathlib import Path

from pipeline.bronze.uploader import BronzeUploader
from pipeline.ingestion.local_reader import read_local_file
from pipeline.ingestion.pdf_reader import read_pdf_metadata, validate_pdf
from pipeline.ingestion.persistence import (
    save_local_document,
    save_pdf_document,
    save_scraped_page,
)
from pipeline.ingestion.scraper import scrape
from pipeline.shared.config import settings
from pipeline.shared.schemas.batch_ingestion_result import (
    BatchIngestionError,
    BatchIngestionResult,
)
from pipeline.shared.schemas.ingestion_result import IngestionResult

logger = logging.getLogger(__name__)


def _normalize_extensions(extensions: list[str]) -> set[str]:
    normalized: set[str] = set()
    for ext in extensions:
        stripped = ext.strip().lower()
        if not stripped:
            continue
        normalized.add(stripped if stripped.startswith(".") else f".{stripped}")
    return normalized


def _list_directory_files(
    source_dir: Path,
    extensions: list[str],
) -> tuple[list[Path], list[Path]]:
    """Return (matched files, all files) under source_dir."""
    ext_list = _normalize_extensions(extensions)
    all_files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    if not ext_list:
        return all_files, all_files

    matched = [path for path in all_files if path.suffix.lower() in ext_list]
    return matched, all_files


class IngestionPipeline:
    """Runs ingestion flows for URLs and local files."""

    def __init__(
        self,
        output_dir: Path | str | None = None,
        uploader: BronzeUploader | None = None,
    ) -> None:
        self._output_dir = Path(output_dir or settings.local_output_dir)
        self._uploader = uploader or BronzeUploader()

    def run(self, url: str) -> IngestionResult:
        """Scrape a URL, persist locally, and upload to MinIO Bronze."""
        logger.info("Starting ingestion for %s", url)

        page = scrape(url)
        local_path = save_scraped_page(page, self._output_dir)

        try:
            minio_object_key = self._uploader.upload_file(local_path)
        except Exception:
            logger.error(
                "Upload failed; local file preserved at %s",
                local_path,
            )
            raise

        result = IngestionResult(
            source_path=str(page.url),
            local_path=local_path,
            minio_object_key=minio_object_key,
            ingested_at=page.scraped_at,
            url=page.url,
        )
        logger.info(
            "Ingestion completed | local_path=%s minio_object_key=%s",
            result.local_path,
            result.minio_object_key,
        )
        return result

    def run_local(self, file_path: Path) -> IngestionResult:
        """Read a local file, persist, and upload to MinIO Bronze."""
        if file_path.suffix.lower() == ".pdf":
            return self._run_local_pdf(file_path)
        return self._run_local_text(file_path)

    def _run_local_text(self, file_path: Path) -> IngestionResult:
        """Ingest a text or Markdown file."""
        logger.info("Starting local ingestion for %s", file_path)

        doc = read_local_file(file_path)
        local_path = save_local_document(doc, self._output_dir)
        file_stem = Path(doc.file_name).stem

        try:
            minio_object_key = self._uploader.upload_file(
                local_path,
                file_stem=file_stem,
            )
        except Exception:
            logger.error(
                "Upload failed; local file preserved at %s",
                local_path,
            )
            raise

        result = IngestionResult(
            source_path=doc.source_path,
            local_path=local_path,
            minio_object_key=minio_object_key,
            ingested_at=doc.ingested_at,
        )
        logger.info(
            "Local ingestion completed | local_path=%s minio_object_key=%s",
            result.local_path,
            result.minio_object_key,
        )
        return result

    def _run_local_pdf(self, file_path: Path) -> IngestionResult:
        """Validate a PDF, persist metadata, and upload the original to Bronze."""
        logger.info("Starting PDF ingestion for %s", file_path)

        validate_pdf(file_path)
        doc = read_pdf_metadata(file_path)
        local_path = save_pdf_document(doc, self._output_dir)
        file_stem = Path(doc.file_name).stem
        pdf_path = Path(doc.source_path)

        try:
            minio_object_key = self._uploader.upload_file(
                pdf_path,
                content_type="application/pdf",
                file_stem=file_stem,
                file_extension=".pdf",
            )
        except Exception:
            logger.error(
                "Upload failed; PDF metadata preserved at %s",
                local_path,
            )
            raise

        result = IngestionResult(
            source_path=doc.source_path,
            local_path=local_path,
            minio_object_key=minio_object_key,
            ingested_at=doc.ingested_at,
            source_format=doc.source_format,
            page_count=doc.page_count,
        )
        logger.info(
            "PDF ingestion completed | local_path=%s minio_object_key=%s pages=%s",
            result.local_path,
            result.minio_object_key,
            result.page_count,
        )
        return result

    def ingest_directory(
        self,
        source_dir: Path | str | None = None,
        extensions: list[str] | None = None,
    ) -> BatchIngestionResult:
        """Ingest all matching files under a directory."""
        resolved_dir = Path(source_dir or settings.data_source_dir).resolve()
        ext_list = extensions or settings.extension_list

        if not resolved_dir.is_dir():
            msg = f"Source directory not found: {resolved_dir}"
            raise FileNotFoundError(msg)

        files, all_files = _list_directory_files(resolved_dir, ext_list)

        if not files and all_files:
            skipped_suffixes = sorted(
                {path.suffix for path in all_files if path.suffix}
            )
            logger.warning(
                "No files matched configured extensions | dir=%s extensions=%s "
                "found_suffixes=%s file_count=%s",
                resolved_dir,
                ext_list,
                skipped_suffixes,
                len(all_files),
            )

        results: list[IngestionResult] = []
        errors: list[BatchIngestionError] = []

        for index, file_path in enumerate(files, start=1):
            print(f"[{index}/{len(files)}] Ingesting {file_path}...", flush=True)
            try:
                result = self.run_local(file_path)
                results.append(result)
                print(
                    f"  -> done (minio_key={result.minio_object_key})",
                    flush=True,
                )
            except Exception as exc:
                source = str(file_path.resolve())
                logger.exception("Failed to ingest %s", source)
                errors.append(BatchIngestionError(source_path=source, error=str(exc)))
                print(f"  -> failed: {exc}", flush=True)

        batch = BatchIngestionResult(
            total_files=len(files),
            succeeded=len(results),
            failed=len(errors),
            results=results,
            errors=errors,
        )
        logger.info(
            "Batch ingestion completed | total=%s succeeded=%s failed=%s",
            batch.total_files,
            batch.succeeded,
            batch.failed,
        )
        return batch


def run_ingestion(url: str) -> IngestionResult:
    """Run the full URL ingestion flow using the default pipeline."""
    return IngestionPipeline().run(url)


def run_local_ingestion(file_path: Path) -> IngestionResult:
    """Run local file ingestion using the default pipeline."""
    return IngestionPipeline().run_local(file_path)


def ingest_directory(
    source_dir: Path | str | None = None,
    extensions: list[str] | None = None,
) -> BatchIngestionResult:
    """Ingest all matching files in a directory using the default pipeline."""
    return IngestionPipeline().ingest_directory(source_dir, extensions)
