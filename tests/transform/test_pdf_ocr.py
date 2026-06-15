from unittest.mock import Mock, patch

import fitz
import pytest

from pipeline.transform.pdf_ocr import ocr_page, resolve_page_text


@pytest.fixture
def text_page() -> fitz.Page:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Native PDF text content")
    yield page
    document.close()


def test_needs_ocr_below_threshold(text_page: fitz.Page) -> None:
    with patch("pipeline.transform.pdf_ocr.is_tesseract_available", return_value=True):
        with patch(
            "pipeline.transform.pdf_ocr.ocr_page",
            return_value="OCR recovered enough text for the page",
        ):
            text, method = resolve_page_text(
                text_page,
                "short",
                ocr_enabled=True,
                min_chars=50,
                dpi=200,
                lang="eng",
            )

    assert method == "ocr"
    assert "OCR recovered" in text


def test_ocr_page_returns_text(text_page: fitz.Page) -> None:
    mock_pytesseract = Mock()
    mock_pytesseract.image_to_string.return_value = "Recognized text"

    with patch.dict("sys.modules", {"pytesseract": mock_pytesseract}):
        with patch("pipeline.shared.tesseract_env.configure_pytesseract"):
            text = ocr_page(text_page, dpi=200, lang="eng")

    assert text == "Recognized text"


def test_ocr_disabled_skips(text_page: fitz.Page) -> None:
    text, method = resolve_page_text(
        text_page,
        "short",
        ocr_enabled=False,
        min_chars=50,
        dpi=200,
        lang="eng",
    )

    assert method == "native"
    assert text == "short"
