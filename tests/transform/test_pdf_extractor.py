import pytest

from pipeline.shared.config.settings import Settings
from pipeline.transform.pdf_extractor import extract_pdf_content
from pipeline.transform.pdf_layout import table_to_markdown


def test_table_to_markdown_formats_pipe_table() -> None:
    markdown = table_to_markdown([["Name", "Value"], ["A", "1"], ["B", "2"]])

    assert "| Name | Value |" in markdown
    assert "| --- | --- |" in markdown
    assert "| A | 1 |" in markdown


def test_extract_pdf_content_rejects_non_pdf() -> None:
    with pytest.raises(ValueError, match="Not a PDF file"):
        extract_pdf_content(b"plain text", mode="native")


def test_extract_native_extracts_text(sample_pdf_bytes: bytes) -> None:
    extracted = extract_pdf_content(
        sample_pdf_bytes,
        mode="native",
        file_name="sample.pdf",
    )

    assert "Hello native PDF text" in extracted.markdown
    assert extracted.page_count == 1
    assert extracted.pages_native == 1
    assert "native" in extracted.methods_used


def test_native_and_structured_differ_for_table_pdf(table_pdf_bytes: bytes) -> None:
    native = extract_pdf_content(
        table_pdf_bytes,
        mode="native",
        file_name="sample-table.pdf",
    )
    structured = extract_pdf_content(
        table_pdf_bytes,
        mode="structured",
        file_name="sample-table.pdf",
    )

    assert native.markdown
    assert structured.markdown
    assert structured.tables_count >= 1 or "| Col A |" in structured.markdown
    assert structured.methods_used != native.methods_used or (
        structured.tables_count > 0
    )


def test_extract_respects_max_pages(sample_pdf_bytes: bytes) -> None:
    extracted = extract_pdf_content(
        sample_pdf_bytes,
        mode="native",
        max_pages=1,
        file_name="sample.pdf",
    )

    assert extracted.page_count == 1


def test_extract_raises_for_empty_pdf(tmp_path, monkeypatch) -> None:
    from transform.pdf_fixtures import write_sample_pdf

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
