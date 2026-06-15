"""OCR fallback for PDF pages with insufficient native text."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz

logger = logging.getLogger(__name__)

SERVICE = "pdf_ocr"


def is_tesseract_available() -> bool:
    """Return True when pytesseract and a Tesseract binary are configured."""
    try:
        import pytesseract

        from pipeline.shared.config import settings
        from pipeline.shared.tesseract_env import configure_pytesseract
    except ImportError:
        return False

    if not settings.resolved_tesseract_cmd:
        return False

    try:
        configure_pytesseract()
        pytesseract.get_tesseract_version()
    except Exception:
        return False

    return True


def ocr_page(page: fitz.Page, *, dpi: int, lang: str) -> str:
    """Render a PDF page and run Tesseract OCR."""
    import pytesseract
    from PIL import Image

    from pipeline.shared.tesseract_env import configure_pytesseract

    configure_pytesseract()
    pix = page.get_pixmap(dpi=dpi)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(image, lang=lang).strip()


def resolve_page_text(
    page: fitz.Page,
    native_text: str,
    *,
    ocr_enabled: bool,
    min_chars: int,
    dpi: int,
    lang: str,
) -> tuple[str, str]:
    """Return page text and extraction method (`native` or `ocr`)."""
    stripped = native_text.strip()
    if len(stripped) >= min_chars:
        return stripped, "native"

    if not ocr_enabled:
        logger.warning(
            "Page has insufficient native text and OCR is disabled",
            extra={
                "service": SERVICE,
                "page_number": page.number + 1,
                "native_chars": len(stripped),
            },
        )
        return stripped, "native"

    if not is_tesseract_available():
        logger.error(
            "OCR requested but Tesseract is unavailable",
            extra={"service": SERVICE, "page_number": page.number + 1},
        )
        return stripped, "native"

    try:
        ocr_text = ocr_page(page, dpi=dpi, lang=lang)
    except Exception:
        logger.exception(
            "OCR failed for page",
            extra={"service": SERVICE, "page_number": page.number + 1},
        )
        return stripped, "native"

    if len(ocr_text.strip()) >= min_chars:
        return ocr_text.strip(), "ocr"

    return ocr_text.strip() or stripped, "ocr" if ocr_text.strip() else "native"
