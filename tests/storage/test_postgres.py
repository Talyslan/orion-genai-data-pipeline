from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from pipeline.shared.schemas.processed_document import ProcessedDocument
from pipeline.shared.schemas.text_chunk import TextChunk
from pipeline.storage.postgres import PostgresStore


def _connection_mock(fetchone_result=None) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = fetchone_result
    return conn


@patch("pipeline.storage.postgres.psycopg.connect")
def test_get_document_id_by_hash_returns_uuid(mock_connect: Mock) -> None:
    document_id = uuid4()
    conn = _connection_mock(fetchone_result=(document_id,))
    mock_connect.return_value.__enter__.return_value = conn
    mock_connect.return_value.__exit__.return_value = False

    result = PostgresStore().get_document_id_by_hash("abc123")

    assert result == document_id


@patch("pipeline.storage.postgres.psycopg.connect")
def test_trace_vector_returns_chain(mock_connect: Mock) -> None:
    chunk_id = uuid4()
    document_id = uuid4()
    conn = _connection_mock(
        fetchone_result=(
            chunk_id,
            0,
            "chunk content",
            document_id,
            "sample.txt",
            "/abs/sample.txt",
            "source/2026/06/08/sample.md",
        )
    )
    mock_connect.return_value.__enter__.return_value = conn
    mock_connect.return_value.__exit__.return_value = False

    trace = PostgresStore().trace_vector(chunk_id)

    assert trace.chunk_id == chunk_id
    assert trace.document_id == document_id
    assert trace.source_path == "/abs/sample.txt"
    assert trace.source_format is None


@patch("pipeline.storage.postgres.psycopg.connect")
def test_trace_vector_raises_when_missing(mock_connect: Mock) -> None:
    conn = _connection_mock(fetchone_result=None)
    mock_connect.return_value.__enter__.return_value = conn
    mock_connect.return_value.__exit__.return_value = False

    with pytest.raises(LookupError, match="Chunk not found"):
        PostgresStore().trace_vector(uuid4())


@patch("pipeline.storage.postgres.psycopg.connect")
def test_save_document_and_chunks_commits(mock_connect: Mock) -> None:
    conn = _connection_mock()
    mock_connect.return_value.__enter__.return_value = conn
    mock_connect.return_value.__exit__.return_value = False

    doc = ProcessedDocument(
        source_path="/abs/sample.txt",
        file_name="sample.txt",
        file_hash="hash",
        minio_object_key="source/2026/06/08/sample.md",
        cleaned_content="conteúdo",
        created_at=datetime(2026, 6, 8, 12, 0, tzinfo=UTC),
    )
    chunk = TextChunk(
        document_id=doc.id,
        chunk_index=0,
        content="conteúdo",
        char_start=0,
        char_end=8,
    )

    result = PostgresStore().save_document_and_chunks(doc, [chunk])

    assert result == doc.id
    conn.commit.assert_called_once()
    conn.cursor.return_value.__enter__.return_value.executemany.assert_called_once()
