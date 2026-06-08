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
