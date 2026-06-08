from uuid import uuid4

import pytest

from pipeline.transform.chunker import chunk_text


def test_chunk_text_returns_single_chunk_for_short_text() -> None:
    document_id = uuid4()
    text = "a" * 500

    chunks = chunk_text(text, document_id, chunk_size=1200, overlap=200)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert len(chunks[0].content) == 500


def test_chunk_text_splits_long_text_with_overlap() -> None:
    document_id = uuid4()
    text = "a" * 2500

    chunks = chunk_text(text, document_id, chunk_size=1200, overlap=200)

    assert len(chunks) >= 2
    assert all(len(chunk.content) <= 1200 for chunk in chunks)
    assert chunks[0].content[-200:] == chunks[1].content[:200]


def test_chunk_text_prefers_paragraph_break() -> None:
    document_id = uuid4()
    first = "a" * 900
    second = "b" * 900
    text = f"{first}\n\n{second}"

    chunks = chunk_text(text, document_id, chunk_size=1200, overlap=200)

    assert len(chunks) >= 2
    assert chunks[0].content.endswith("\n\n")


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("texto", uuid4(), chunk_size=1200, overlap=1200)
