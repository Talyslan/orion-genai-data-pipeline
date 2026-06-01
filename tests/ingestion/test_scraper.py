from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError

from pipeline.ingestion.scraper import scrape


@patch("pipeline.ingestion.scraper.requests.get")
def test_scraper_extracts_title_from_html(mock_get: Mock, sample_html: str) -> None:
    mock_response = Mock()
    mock_response.text = sample_html
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    page = scrape("https://example.com")

    assert str(page.url) == "https://example.com/"
    assert page.title == "Test Page"
    assert "<p>Hello</p>" in page.content
    mock_get.assert_called_once_with(
        "https://example.com",
        timeout=30,
        headers={"User-Agent": "OrionDataPipeline/0.1"},
    )


@patch("pipeline.ingestion.scraper.requests.get")
def test_scraper_uses_untitled_when_title_missing(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.text = "<html><body><p>No title</p></body></html>"
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    page = scrape("https://example.com")

    assert page.title == "Untitled"


@patch("pipeline.ingestion.scraper.requests.get")
def test_scraper_raises_on_http_404(mock_get: Mock) -> None:
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)
    mock_get.return_value = mock_response

    with pytest.raises(HTTPError):
        scrape("https://example.com/not-found")


def test_scraper_raises_on_invalid_url() -> None:
    with pytest.raises(ValueError, match="Invalid URL"):
        scrape("not-a-valid-url")
