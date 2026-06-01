"""Local file persistence for scraped content."""

from pathlib import Path

from pipeline.shared.schemas.scraped_page import ScrapedPage


def save_scraped_page(page: ScrapedPage, output_dir: Path) -> Path:
    """Save a scraped page as Markdown and return the absolute file path."""
    raise NotImplementedError
