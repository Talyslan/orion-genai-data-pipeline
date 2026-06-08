from unittest.mock import Mock, patch
from uuid import uuid4

from pipeline.shared.schemas.chunk_embedding import ChunkEmbedding
from pipeline.shared.schemas.text_chunk import TextChunk
from pipeline.transform.bronze_reader import BronzeObject
from pipeline.transform.pipeline import TransformPipeline


def _bronze_object() -> BronzeObject:
    return BronzeObject(
        object_key="source/2026/06/08/sample-prompt.md",
        source_path="/abs/path/sample-prompt.txt",
        file_name="sample-prompt.txt",
        body="# sample-prompt\n\nConteúdo de teste",
        raw_content="raw",
    )


@patch("pipeline.transform.pipeline.QdrantStore")
@patch("pipeline.transform.pipeline.PostgresStore")
@patch("pipeline.transform.pipeline.Embedder")
@patch("pipeline.transform.pipeline.chunk_text")
@patch("pipeline.transform.pipeline.clean_content")
@patch("pipeline.transform.pipeline.BronzeReader")
def test_process_object_runs_full_transform_flow(
    mock_reader_cls: Mock,
    mock_clean: Mock,
    mock_chunk_text: Mock,
    mock_embedder_cls: Mock,
    mock_postgres_cls: Mock,
    mock_qdrant_cls: Mock,
) -> None:
    document_id = uuid4()
    chunk_id = uuid4()

    mock_reader = Mock()
    mock_reader.fetch_object.return_value = _bronze_object()
    mock_reader_cls.return_value = mock_reader

    mock_clean.return_value = "Conteúdo de teste"
    chunk = TextChunk(
        id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        content="Conteúdo de teste",
        char_start=0,
        char_end=16,
    )
    mock_chunk_text.return_value = [chunk]

    mock_embedder = Mock()
    mock_embedder.embed_chunks.return_value = [
        ChunkEmbedding(chunk_id=chunk_id, vector=[0.1] * 1024),
    ]
    mock_embedder_cls.return_value = mock_embedder

    mock_postgres = Mock()
    mock_postgres.get_document_id_by_hash.return_value = None
    mock_postgres_cls.return_value = mock_postgres

    mock_qdrant = Mock()
    mock_qdrant_cls.return_value = mock_qdrant

    pipeline = TransformPipeline(
        reader=mock_reader,
        embedder=mock_embedder,
        postgres=mock_postgres,
        qdrant=mock_qdrant,
    )

    result = pipeline.process_object("source/2026/06/08/sample-prompt.md")

    assert result.skipped is False
    assert result.chunks_count == 1
    assert result.embeddings_count == 1
    mock_postgres.save_document_and_chunks.assert_called_once()
    mock_qdrant.upsert_embeddings.assert_called_once()


@patch("pipeline.transform.pipeline.QdrantStore")
@patch("pipeline.transform.pipeline.PostgresStore")
@patch("pipeline.transform.pipeline.Embedder")
@patch("pipeline.transform.pipeline.BronzeReader")
def test_process_object_skips_existing_hash(
    mock_reader_cls: Mock,
    mock_embedder_cls: Mock,
    mock_postgres_cls: Mock,
    mock_qdrant_cls: Mock,
) -> None:
    existing_id = uuid4()

    mock_reader = Mock()
    mock_reader.fetch_object.return_value = _bronze_object()
    mock_reader_cls.return_value = mock_reader

    mock_postgres = Mock()
    mock_postgres.get_document_id_by_hash.return_value = existing_id
    mock_postgres_cls.return_value = mock_postgres

    pipeline = TransformPipeline(
        reader=mock_reader,
        embedder=mock_embedder_cls.return_value,
        postgres=mock_postgres,
        qdrant=mock_qdrant_cls.return_value,
    )

    result = pipeline.process_object("source/2026/06/08/sample-prompt.md")

    assert result.skipped is True
    assert result.document_id == existing_id
    mock_postgres.save_document_and_chunks.assert_not_called()
    mock_qdrant_cls.return_value.upsert_embeddings.assert_not_called()
