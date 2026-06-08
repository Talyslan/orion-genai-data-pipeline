"""Read local text files for batch ingestion."""

import logging
from pathlib import Path

from pipeline.shared.schemas.local_document import LocalDocument

logger = logging.getLogger(__name__)

SERVICE = "local_reader"


def _read_text(file_path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    msg = f"Unable to decode file as UTF-8: {file_path}"
    raise ValueError(msg)


def read_local_file(file_path: Path) -> LocalDocument:
    """Read a local file and return a LocalDocument with metadata."""
    resolved = file_path.resolve()

    if not resolved.is_file():
        msg = f"File not found: {resolved}"
        raise FileNotFoundError(msg)

    logger.info(
        "Reading local file",
        extra={"service": SERVICE, "source_path": str(resolved)},
    )

    try:
        content = _read_text(resolved)
    except OSError:
        logger.exception(
            "Failed to read local file",
            extra={"service": SERVICE, "source_path": str(resolved)},
        )
        raise

    if not content.strip():
        logger.warning(
            "Empty file content",
            extra={"service": SERVICE, "source_path": str(resolved)},
        )

    title = resolved.stem
    doc = LocalDocument(
        source_path=str(resolved),
        file_name=resolved.name,
        title=title,
        content=content,
    )

    logger.info(
        "Local file read",
        extra={"service": SERVICE, "source_path": str(resolved)},
    )

    return doc
