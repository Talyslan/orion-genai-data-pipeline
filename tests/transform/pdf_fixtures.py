"""Build PDF fixtures for transform extraction tests."""

from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image, ImageDraw


def write_sample_pdf(
    path: Path,
    text: str = "Hello native PDF text for extraction",
) -> Path:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path


def write_table_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page()
    for y in (72, 122, 172):
        page.draw_line((72, y), (372, y))
    for x in (72, 172, 272, 372):
        page.draw_line((x, 72), (x, 172))
    page.insert_text((80, 80), "Col A", fontsize=10)
    page.insert_text((180, 80), "Col B", fontsize=10)
    page.insert_text((280, 80), "Col C", fontsize=10)
    page.insert_text((80, 130), "1", fontsize=10)
    page.insert_text((180, 130), "2", fontsize=10)
    page.insert_text((280, 130), "3", fontsize=10)
    document.save(path)
    document.close()
    return path


def write_scanned_pdf(path: Path, text: str = "Scanned OCR text") -> Path:
    document = fitz.open()
    page = document.new_page()
    image = Image.new("RGB", (400, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 40), text, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    page.insert_image(page.rect, stream=buffer.getvalue())
    document.save(path)
    document.close()
    return path


def ensure_pdf_fixtures(fixtures_dir: Path) -> dict[str, Path]:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "sample": fixtures_dir / "sample.pdf",
        "table": fixtures_dir / "sample-table.pdf",
        "scanned": fixtures_dir / "sample-scanned.pdf",
    }
    write_sample_pdf(paths["sample"])
    write_table_pdf(paths["table"])
    write_scanned_pdf(paths["scanned"])
    return paths
