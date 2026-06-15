import pytest

from pipeline.shared.config.settings import PDF_EXTRACTION_MODES, Settings


def test_pdf_settings_defaults_match_spec() -> None:
    settings = Settings()

    assert settings.data_source_dir == "./pdfs"
    assert settings.data_source_extensions == ".txt,.md,.pdf"
    assert settings.pdf_extractor == "pymupdf"
    assert settings.pdf_extraction_mode == "structured"
    assert settings.pdf_max_pages == 0
    assert settings.pdf_ocr_enabled is True
    assert settings.pdf_ocr_min_chars == 50
    assert settings.pdf_ocr_lang == "eng+por"
    assert settings.pdf_ocr_dpi == 200
    assert settings.pdf_extract_tables is True
    assert settings.pdf_figure_placeholder is True
    assert settings.pdf_manifest_path == "./pdfs/manifest.yaml"
    assert settings.pdf_download_dir == "./pdfs"
    assert settings.pdf_download_skip_existing is True


def test_extension_list_includes_pdf() -> None:
    settings = Settings()

    assert settings.extension_list == [".txt", ".md", ".pdf"]


@pytest.mark.parametrize("mode", sorted(PDF_EXTRACTION_MODES))
def test_pdf_extraction_mode_accepts_valid_values(mode: str) -> None:
    settings = Settings(pdf_extraction_mode=mode)

    assert settings.pdf_extraction_mode == mode


def test_pdf_extraction_mode_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="PDF_EXTRACTION_MODE"):
        Settings(pdf_extraction_mode="invalid")


def test_pdf_max_pages_rejects_negative() -> None:
    with pytest.raises(ValueError, match="PDF_MAX_PAGES"):
        Settings(pdf_max_pages=-1)


def test_pdf_ocr_min_chars_rejects_zero() -> None:
    with pytest.raises(ValueError, match="PDF OCR settings"):
        Settings(pdf_ocr_min_chars=0)
