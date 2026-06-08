"""Text chunking with configurable size and overlap."""

import logging
from uuid import UUID

from pipeline.shared.config import settings
from pipeline.shared.schemas.text_chunk import TextChunk

logger = logging.getLogger(__name__)

SERVICE = "chunker"

_BREAK_DELIMITERS = ("\n\n", ". ", "! ", "? ", " ")


def _find_break_point(text: str, start: int, end: int) -> int:
    window = text[start:end]
    for delimiter in _BREAK_DELIMITERS:
        index = window.rfind(delimiter)
        if index > 0:
            return start + index + len(delimiter)
    return end


def chunk_text(
    text: str,
    document_id: UUID,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[TextChunk]:
    """Split text into chunks with overlap."""
    size = chunk_size or settings.chunk_size
    overlap_size = overlap or settings.chunk_overlap

    if overlap_size >= size:
        msg = f"overlap ({overlap_size}) must be less than chunk_size ({size})"
        raise ValueError(msg)

    if not text.strip():
        return []

    chunks: list[TextChunk] = []
    pos = 0
    index = 0

    while pos < len(text):
        end = min(pos + size, len(text))
        if end < len(text):
            end = _find_break_point(text, pos, end)

        content = text[pos:end]
        chunks.append(
            TextChunk(
                document_id=document_id,
                chunk_index=index,
                content=content,
                char_start=pos,
                char_end=end,
            )
        )

        if end >= len(text):
            break

        next_pos = end - overlap_size
        if next_pos <= pos:
            next_pos = end
        pos = next_pos
        index += 1

    logger.info(
        "Chunks generated",
        extra={
            "service": SERVICE,
            "count": len(chunks),
            "chunk_size": size,
            "overlap": overlap_size,
        },
    )
    return chunks
