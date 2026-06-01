"""Orchestration of scrape → local persistence → MinIO Bronze upload."""

import logging
from pathlib import Path

from pipeline.bronze.uploader import BronzeUploader
from pipeline.ingestion.persistence import save_scraped_page
from pipeline.ingestion.scraper import scrape
from pipeline.shared.config import settings
from pipeline.shared.schemas.ingestion_result import IngestionResult

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Runs the ingestion flow for a single URL."""

    def __init__(
        self,
        output_dir: Path | str | None = None,
        uploader: BronzeUploader | None = None,
    ) -> None:
        self._output_dir = Path(output_dir or settings.local_output_dir)
        self._uploader = uploader or BronzeUploader()

    def run(self, url: str) -> IngestionResult:
        """Scrape, persist locally, and upload to MinIO Bronze."""
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
            url=page.url,
            local_path=local_path,
            minio_object_key=minio_object_key,
            scraped_at=page.scraped_at,
        )
        logger.info(
            "Ingestion completed | local_path=%s minio_object_key=%s",
            result.local_path,
            result.minio_object_key,
        )
        return result


def run_ingestion(url: str) -> IngestionResult:
    """Run the full ingestion flow using the default pipeline."""
    return IngestionPipeline().run(url)
