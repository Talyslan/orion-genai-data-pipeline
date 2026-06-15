from unittest.mock import Mock, patch
from uuid import uuid4

from pdf_fixtures import write_sample_pdf, write_table_pdf

from pipeline.shared.config.settings import Settings
from pipeline.shared.schemas.chunk_embedding import ChunkEmbedding
from pipeline.shared.schemas.text_chunk import TextChunk
from pipeline.transform.bronze_reader import BronzeObject
from pipeline.transform.pipeline import TransformPipeline, trace_vector


def _pdf_bronze_object(pdf_bytes: bytes, object_key: str) -> BronzeObject:
    return BronzeObject(
        object_key=object_key,
        source_path="/data/pdfs/wellarchitected-framework.pdf",
        file_name="wellarchitected-framework.pdf",
        body="",
        raw_content="",
        content_type="application/pdf",
        raw_bytes=pdf_bytes,
    )


@patch("pipeline.transform.pipeline.settings", Settings(pdf_ocr_enabled=False))
@patch("pipeline.transform.pipeline.QdrantStore")
@patch("pipeline.transform.pipeline.PostgresStore")
@patch("pipeline.transform.pipeline.Embedder")
@patch("pipeline.transform.pipeline.BronzeReader")
def test_process_object_pdf_end_to_end(
    mock_reader_cls: Mock,
    mock_embedder_cls: Mock,
    mock_postgres_cls: Mock,
    mock_qdrant_cls: Mock,
    tmp_path,
) -> None:
    pdf_path = tmp_path / "doc.pdf"
    write_sample_pdf(pdf_path, text="AWS Well-Architected Framework content")
    pdf_bytes = pdf_path.read_bytes()
    object_key = "source/2026/06/15/wellarchitected-framework.pdf"

    mock_reader = Mock()
    mock_reader.fetch_object.return_value = _pdf_bronze_object(pdf_bytes, object_key)
    mock_reader_cls.return_value = mock_reader

    chunk_id = uuid4()
    mock_postgres = Mock()
    mock_postgres.get_document_id_by_hash.return_value = None
    mock_postgres_cls.return_value = mock_postgres

    mock_embedder = Mock()
    mock_embedder.embed_chunks.return_value = [
        ChunkEmbedding(chunk_id=chunk_id, vector=[0.1] * 1024),
    ]
    mock_embedder_cls.return_value = mock_embedder

    mock_qdrant = Mock()
    mock_qdrant_cls.return_value = mock_qdrant

    pipeline = TransformPipeline(
        reader=mock_reader,
        embedder=mock_embedder,
        postgres=mock_postgres,
        qdrant=mock_qdrant,
    )

    result = pipeline.process_object(object_key)

    assert result.skipped is False
    assert result.chunks_count >= 1
    saved_doc = mock_postgres.save_document_and_chunks.call_args[0][0]
    assert saved_doc.source_format == "pdf"
    assert saved_doc.extraction_metadata is not None

    payloads = mock_qdrant.upsert_embeddings.call_args[0][1]
    assert payloads[0]["source_format"] == "pdf"
    assert payloads[0]["file_name"] == "wellarchitected-framework.pdf"


@patch("pipeline.transform.pipeline.settings", Settings(pdf_ocr_enabled=False))
@patch("pipeline.transform.pipeline.QdrantStore")
@patch("pipeline.transform.pipeline.PostgresStore")
@patch("pipeline.transform.pipeline.Embedder")
@patch("pipeline.transform.pipeline.BronzeReader")
def test_process_pdf_with_table_produces_pipe_table_chunks(
    mock_reader_cls: Mock,
    mock_embedder_cls: Mock,
    mock_postgres_cls: Mock,
    mock_qdrant_cls: Mock,
    tmp_path,
) -> None:
    pdf_path = tmp_path / "table.pdf"
    write_table_pdf(pdf_path)
    pdf_bytes = pdf_path.read_bytes()
    object_key = "source/2026/06/15/sample-table.pdf"

    mock_reader = Mock()
    mock_reader.fetch_object.return_value = BronzeObject(
        object_key=object_key,
        source_path=str(pdf_path),
        file_name="sample-table.pdf",
        body="",
        raw_content="",
        content_type="application/pdf",
        raw_bytes=pdf_bytes,
    )
    mock_reader_cls.return_value = mock_reader

    mock_postgres = Mock()
    mock_postgres.get_document_id_by_hash.return_value = None
    mock_postgres_cls.return_value = mock_postgres

    chunk_id = uuid4()
    captured_chunks: list[TextChunk] = []

    def _capture_chunks(text: str, document_id):
        chunks = [
            TextChunk(
                document_id=document_id,
                chunk_index=0,
                content=text,
                char_start=0,
                char_end=len(text),
            )
        ]
        captured_chunks.extend(chunks)
        return chunks

    mock_embedder = Mock()
    mock_embedder.embed_chunks.side_effect = lambda chunks: [
        ChunkEmbedding(chunk_id=chunk_id, vector=[0.1] * 1024)
    ]
    mock_embedder_cls.return_value = mock_embedder

    pipeline = TransformPipeline(
        reader=mock_reader,
        embedder=mock_embedder,
        postgres=mock_postgres,
        qdrant=mock_qdrant_cls.return_value,
    )

    with patch("pipeline.transform.pipeline.chunk_text", side_effect=_capture_chunks):
        pipeline.process_object(object_key)

    assert captured_chunks
    assert "|" in captured_chunks[0].content


@patch("pipeline.storage.postgres.psycopg.connect")
def test_trace_vector_from_pdf_chunk(mock_connect: Mock) -> None:
    chunk_id = uuid4()
    document_id = uuid4()
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = (
        chunk_id,
        0,
        "chunk content",
        document_id,
        "wellarchitected-framework.pdf",
        "/data/pdfs/wellarchitected-framework.pdf",
        "source/2026/06/15/wellarchitected-framework.pdf",
    )
    mock_connect.return_value.__enter__.return_value = conn
    mock_connect.return_value.__exit__.return_value = False

    trace = trace_vector(chunk_id)

    assert trace.source_format == "pdf"
    assert trace.file_name.endswith(".pdf")
    assert trace.minio_object_key.endswith(".pdf")
