from unittest.mock import Mock, patch

import pytest

from pipeline.shared.config.settings import Settings
from pipeline.transform.pdf_extractor import extract_pdf_content


def test_extract_pdf_content_rejects_non_pdf() -> None:
    with pytest.raises(ValueError, match="Not a PDF file"):
        extract_pdf_content(b"plain text", mode="native")


def test_extract_native_mode(sample_pdf_bytes: bytes) -> None:
    extracted = extract_pdf_content(
        sample_pdf_bytes,
        mode="native",
        file_name="sample.pdf",
    )

    assert "Hello native PDF text" in extracted.markdown
    assert extracted.page_count == 1
    assert extracted.pages_native == 1
    assert "native" in extracted.methods_used


def test_extract_structured_mode_includes_tables(table_pdf_bytes: bytes) -> None:
    extracted = extract_pdf_content(
        table_pdf_bytes,
        mode="structured",
        file_name="sample-table.pdf",
    )

    assert extracted.markdown
    assert extracted.tables_count >= 1 or "| Col A |" in extracted.markdown
    assert "pdfplumber" in extracted.methods_used


def test_extract_text_respects_max_pages(sample_pdf_bytes: bytes) -> None:
    extracted = extract_pdf_content(
        sample_pdf_bytes,
        mode="native",
        max_pages=1,
        file_name="sample.pdf",
    )

    assert extracted.page_count == 1


@patch("pipeline.transform.pdf_layout.resolve_page_text")
def test_ocr_fallback_on_scanned_page(
    mock_resolve: Mock,
    scanned_pdf_bytes: bytes,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "pipeline.transform.pdf_extractor.settings",
        Settings(pdf_ocr_enabled=True, pdf_ocr_min_chars=10),
    )
    mock_resolve.return_value = ("Scanned OCR text for fallback", "ocr")

    extracted = extract_pdf_content(
        scanned_pdf_bytes,
        mode="native",
        file_name="sample-scanned.pdf",
    )

    assert extracted.pages_ocr >= 1
    assert "ocr" in extracted.methods_used


def test_figure_placeholder_inserted(scanned_pdf_bytes: bytes, monkeypatch) -> None:
    monkeypatch.setattr(
        "pipeline.transform.pdf_extractor.settings",
        Settings(
            pdf_ocr_enabled=False,
            pdf_ocr_min_chars=500,
            pdf_figure_placeholder=True,
        ),
    )

    extracted = extract_pdf_content(
        scanned_pdf_bytes,
        mode="structured",
        file_name="sample-scanned.pdf",
    )

    assert extracted.figures_count >= 1 or "![figure page" in extracted.markdown


def test_extract_raises_for_empty_pdf(tmp_path, monkeypatch) -> None:
    from pdf_fixtures import write_sample_pdf

    empty_pdf = tmp_path / "empty.pdf"
    write_sample_pdf(empty_pdf, text="   ")

    test_settings = Settings(pdf_ocr_enabled=False)
    monkeypatch.setattr("pipeline.transform.pdf_extractor.settings", test_settings)

    with pytest.raises(ValueError, match="empty content"):
        extract_pdf_content(
            empty_pdf.read_bytes(),
            mode="native",
            file_name="empty.pdf",
        )
