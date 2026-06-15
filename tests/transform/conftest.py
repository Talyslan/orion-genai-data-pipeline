from pathlib import Path

import pytest
from transform.pdf_fixtures import ensure_pdf_fixtures


@pytest.fixture
def pdf_fixture_paths(fixtures_dir: Path) -> dict[str, Path]:
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
