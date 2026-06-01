from pathlib import Path

from pipeline.ingestion.persistence import save_scraped_page
from pipeline.shared.schemas.scraped_page import ScrapedPage


def test_save_scraped_page_writes_markdown_file(
    scraped_page: ScrapedPage,
    tmp_output_dir: Path,
) -> None:
    saved_path = save_scraped_page(scraped_page, tmp_output_dir)

    assert saved_path.is_absolute()
    assert saved_path.exists()
    assert saved_path.suffix == ".md"
    assert saved_path.parent == tmp_output_dir.resolve()

    content = saved_path.read_text(encoding="utf-8")
    assert content == scraped_page.to_markdown()


def test_save_scraped_page_creates_output_directory(
    scraped_page: ScrapedPage,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "nested" / "local"

    saved_path = save_scraped_page(scraped_page, output_dir)

    assert output_dir.exists()
    assert saved_path.exists()


def test_save_scraped_page_generates_markdown_format(
    scraped_page: ScrapedPage,
    tmp_output_dir: Path,
) -> None:
    saved_path = save_scraped_page(scraped_page, tmp_output_dir)
    content = saved_path.read_text(encoding="utf-8")

    assert content.startswith("# Example Page\n\n")
    assert "**URL:** https://example.com/" in content
    assert "**Coletado em:**" in content
    assert "---\n\n<body><p>Hello world</p></body>" in content
