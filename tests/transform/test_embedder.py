from unittest.mock import Mock, patch
from uuid import uuid4

import numpy as np

from pipeline.shared.schemas.text_chunk import TextChunk
from pipeline.transform.embedder import Embedder


@patch("pipeline.transform.embedder._get_model")
def test_embed_chunks_returns_vectors_with_dimension_1024(mock_get_model: Mock) -> None:
    mock_model = Mock()
    mock_model.encode.return_value = np.array([[0.1] * 1024, [0.2] * 1024])
    mock_get_model.return_value = mock_model

    document_id = uuid4()
    chunks = [
        TextChunk(
            document_id=document_id,
            chunk_index=0,
            content="Primeiro chunk",
            char_start=0,
            char_end=14,
        ),
        TextChunk(
            document_id=document_id,
            chunk_index=1,
            content="Segundo chunk",
            char_start=14,
            char_end=27,
        ),
    ]

    embeddings = Embedder().embed_chunks(chunks)

    assert len(embeddings) == 2
    assert len(embeddings[0].vector) == 1024
    assert embeddings[0].chunk_id == chunks[0].id
    assert embeddings[0].model == "BAAI/bge-m3"


@patch("pipeline.transform.embedder._get_model")
def test_embed_chunks_skips_empty_content(mock_get_model: Mock) -> None:
    document_id = uuid4()
    chunks = [
        TextChunk(
            document_id=document_id,
            chunk_index=0,
            content="   ",
            char_start=0,
            char_end=3,
        ),
    ]

    embeddings = Embedder().embed_chunks(chunks)

    assert embeddings == []
    mock_get_model.assert_not_called()
