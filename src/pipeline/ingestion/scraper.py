"""HTTP client and HTML parsing for web scraping."""

import logging
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError, RequestException, Timeout

from pipeline.shared.config import settings
from pipeline.shared.schemas.scraped_page import ScrapedPage

logger = logging.getLogger(__name__)

USER_AGENT = "OrionDataPipeline/0.1"
SERVICE = "scraper"


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        msg = f"Invalid URL: {url}"
        raise ValueError(msg)
    return url


def _extract_title(soup: BeautifulSoup) -> str:
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        stripped = title_tag.string.strip()
        if stripped:
            return stripped
    return "Untitled"


def _extract_content(soup: BeautifulSoup) -> str:
    body = soup.find("body")
    if body is None:
        return ""
    return str(body)


def scrape(url: str) -> ScrapedPage:
    """Fetch a URL and extract title and content from the page."""
    try:
        validated_url = _validate_url(url)
    except ValueError:
        logger.error(
            "Invalid URL",
            extra={"service": SERVICE, "url": url},
        )
        raise

    logger.info(
        "Starting page scrape",
        extra={"service": SERVICE, "url": validated_url},
    )

    try:
        response = requests.get(
            validated_url,
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except Timeout:
        logger.error(
            "Request timed out",
            extra={"service": SERVICE, "url": validated_url},
        )
        raise
    except HTTPError:
        logger.error(
            "HTTP error while scraping page",
            extra={"service": SERVICE, "url": validated_url},
        )
        raise
    except RequestException:
        logger.error(
            "Request failed",
            extra={"service": SERVICE, "url": validated_url},
        )
        raise

    if not response.text.strip():
        logger.warning(
            "Empty HTML response",
            extra={"service": SERVICE, "url": validated_url},
        )
        return ScrapedPage(url=validated_url, title="Untitled", content="")

    soup = BeautifulSoup(response.text, "lxml")
    title = _extract_title(soup)
    content = _extract_content(soup)

    logger.info(
        "Page scraped",
        extra={"service": SERVICE, "url": validated_url},
    )

    return ScrapedPage(url=validated_url, title=title, content=content)
