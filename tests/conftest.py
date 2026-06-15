from pathlib import Path

import pytest

from pipeline.shared.schemas.scraped_page import ScrapedPage


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_html() -> str:
    return """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body><p>Hello</p></body>
</html>"""


@pytest.fixture
def scraped_page() -> ScrapedPage:
    return ScrapedPage(
        url="https://example.com",
        title="Example Page",
        content="<body><p>Hello world</p></body>",
    )


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    return tmp_path / "local"


@pytest.fixture
def pdf_fixture_paths(fixtures_dir: Path) -> dict[str, Path]:
    from pdf_fixtures import ensure_pdf_fixtures

    return ensure_pdf_fixtures(fixtures_dir)


@pytest.fixture
def sample_pdf_bytes(pdf_fixture_paths: dict[str, Path]) -> bytes:
    return pdf_fixture_paths["sample"].read_bytes()


@pytest.fixture
def table_pdf_bytes(pdf_fixture_paths: dict[str, Path]) -> bytes:
    return pdf_fixture_paths["table"].read_bytes()


@pytest.fixture
def scanned_pdf_bytes(pdf_fixture_paths: dict[str, Path]) -> bytes:
    return pdf_fixture_paths["scanned"].read_bytes()


@pytest.fixture
def bronze_pdf_bytes(pdf_fixture_paths: dict[str, Path]) -> bytes:
    return pdf_fixture_paths["bronze"].read_bytes()
