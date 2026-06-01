from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError

from pipeline.ingestion.pipeline import IngestionPipeline, run_ingestion
from pipeline.shared.schemas.scraped_page import ScrapedPage


@patch("pipeline.ingestion.pipeline.save_scraped_page")
@patch("pipeline.ingestion.pipeline.scrape")
def test_ingestion_pipeline_runs_full_flow(
    mock_scrape: Mock,
    mock_save: Mock,
    scraped_page: ScrapedPage,
    tmp_output_dir: Path,
) -> None:
    mock_scrape.return_value = scraped_page
    local_path = tmp_output_dir / "page.md"
    mock_save.return_value = local_path

    mock_uploader = Mock()
    mock_uploader.upload_file.return_value = "source/2026/06/01/page.md"

    pipeline = IngestionPipeline(
        output_dir=tmp_output_dir,
        uploader=mock_uploader,
    )
    result = pipeline.run("https://example.com")

    mock_scrape.assert_called_once_with("https://example.com")
    mock_save.assert_called_once_with(scraped_page, tmp_output_dir)
    mock_uploader.upload_file.assert_called_once_with(local_path)
    assert result.url == scraped_page.url
    assert result.local_path == local_path
    assert result.minio_object_key == "source/2026/06/01/page.md"
    assert result.scraped_at == scraped_page.scraped_at


@patch("pipeline.ingestion.pipeline.save_scraped_page")
@patch("pipeline.ingestion.pipeline.scrape")
def test_ingestion_pipeline_aborts_when_scraper_fails(
    mock_scrape: Mock,
    mock_save: Mock,
    tmp_output_dir: Path,
) -> None:
    mock_scrape.side_effect = HTTPError("404 Not Found")
    mock_uploader = Mock()

    pipeline = IngestionPipeline(
        output_dir=tmp_output_dir,
        uploader=mock_uploader,
    )

    with pytest.raises(HTTPError):
        pipeline.run("https://example.com/not-found")

    mock_save.assert_not_called()
    mock_uploader.upload_file.assert_not_called()


@patch("pipeline.ingestion.pipeline.save_scraped_page")
@patch("pipeline.ingestion.pipeline.scrape")
def test_ingestion_pipeline_aborts_upload_when_persistence_fails(
    mock_scrape: Mock,
    mock_save: Mock,
    scraped_page: ScrapedPage,
    tmp_output_dir: Path,
) -> None:
    mock_scrape.return_value = scraped_page
    mock_save.side_effect = OSError("disk full")
    mock_uploader = Mock()

    pipeline = IngestionPipeline(
        output_dir=tmp_output_dir,
        uploader=mock_uploader,
    )

    with pytest.raises(OSError):
        pipeline.run("https://example.com")

    mock_uploader.upload_file.assert_not_called()


@patch("pipeline.ingestion.pipeline.save_scraped_page")
@patch("pipeline.ingestion.pipeline.scrape")
def test_ingestion_pipeline_preserves_local_file_when_upload_fails(
    mock_scrape: Mock,
    mock_save: Mock,
    scraped_page: ScrapedPage,
    tmp_output_dir: Path,
) -> None:
    mock_scrape.return_value = scraped_page
    local_path = tmp_output_dir / "page.md"
    mock_save.return_value = local_path

    mock_uploader = Mock()
    mock_uploader.upload_file.side_effect = RuntimeError("MinIO unavailable")

    pipeline = IngestionPipeline(
        output_dir=tmp_output_dir,
        uploader=mock_uploader,
    )

    with pytest.raises(RuntimeError, match="MinIO unavailable"):
        pipeline.run("https://example.com")

    mock_uploader.upload_file.assert_called_once_with(local_path)


@patch("pipeline.ingestion.pipeline.IngestionPipeline")
def test_run_ingestion_delegates_to_default_pipeline(mock_pipeline_cls: Mock) -> None:
    mock_instance = Mock()
    mock_pipeline_cls.return_value = mock_instance

    run_ingestion("https://example.com")

    mock_pipeline_cls.assert_called_once_with()
    mock_instance.run.assert_called_once_with("https://example.com")
