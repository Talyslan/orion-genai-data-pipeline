"""Configure pytesseract to use the project-local Tesseract on Windows."""

from __future__ import annotations

import os


def configure_pytesseract() -> None:
    """Point pytesseract at TESSERACT_CMD / .venv/share/tesseract when configured."""
    import pytesseract

    from pipeline.shared.config import settings

    cmd = settings.resolved_tesseract_cmd
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    prefix = settings.resolved_tessdata_prefix
    if prefix:
        os.environ.setdefault("TESSDATA_PREFIX", prefix)
