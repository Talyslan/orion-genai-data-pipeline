"""HTTP client and HTML parsing for web scraping."""

from pipeline.shared.schemas.scraped_page import ScrapedPage


def scrape(url: str) -> ScrapedPage:
    """Fetch a URL and extract title and content from the page."""
    raise NotImplementedError
