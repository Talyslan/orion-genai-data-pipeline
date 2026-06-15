from unittest.mock import patch

import fitz
import pytest

from pipeline.transform.pdf_router import extract_unstructured, route_extraction


def test_unstructured_falls_back_to_structured(sample_pdf_bytes: bytes) -> None:
    with patch(
        "pipeline.transform.pdf_router.partition_pdf",
        create=True,
        side_effect=ImportError,
    ):
        extracted = extract_unstructured(
            sample_pdf_bytes,
            settings=_test_settings(),
            max_pages=0,
        )

    assert "pdfplumber" in extracted.methods_used
    assert extracted.markdown


def test_route_extraction_rejects_unknown_mode(sample_pdf_bytes: bytes) -> None:
    with pytest.raises(ValueError, match="Unsupported PDF extraction mode"):
        route_extraction(
            sample_pdf_bytes,
            mode="invalid",
            max_pages=0,
            settings=_test_settings(),
        )


def _test_settings():
    from pipeline.shared.config.settings import Settings

    return Settings(pdf_ocr_enabled=False)


def test_route_native_handles_password_protected_pdf() -> None:
    document = fitz.open()
    document.new_page()
    buffer = document.write(
        encryption=fitz.PDF_ENCRYPT_AES_128,
        user_pw="secret",
    )
    document.close()

    from pipeline.transform.pdf_extractor import extract_pdf_content

    with pytest.raises(ValueError, match="password-protected"):
        extract_pdf_content(buffer, mode="native", file_name="protected.pdf")
