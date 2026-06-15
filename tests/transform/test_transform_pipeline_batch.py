from unittest.mock import Mock, patch
from uuid import uuid4

from pipeline.shared.schemas.transform_result import TransformResult
from pipeline.transform.pipeline import TransformPipeline


@patch("pipeline.transform.pipeline.QdrantStore")
@patch("pipeline.transform.pipeline.PostgresStore")
@patch("pipeline.transform.pipeline.Embedder")
@patch("pipeline.transform.pipeline.BronzeReader")
def test_run_continues_when_individual_object_fails(
    mock_reader_cls: Mock,
    mock_embedder_cls: Mock,
    mock_postgres_cls: Mock,
    mock_qdrant_cls: Mock,
) -> None:
    mock_reader = Mock()
    mock_reader.list_objects.return_value = [
        "source/2026/06/15/good.pdf",
        "source/2026/06/15/bad.pdf",
    ]
    mock_reader_cls.return_value = mock_reader

    mock_postgres = Mock()
    mock_postgres.get_document_id_by_hash.return_value = None
    mock_postgres_cls.return_value = mock_postgres

    pipeline = TransformPipeline(
        reader=mock_reader,
        embedder=mock_embedder_cls.return_value,
        postgres=mock_postgres,
        qdrant=mock_qdrant_cls.return_value,
    )

    with patch.object(
        pipeline,
        "process_object",
        side_effect=[
            TransformResult(
                object_key="source/2026/06/15/good.pdf",
                document_id=uuid4(),
                chunks_count=2,
                embeddings_count=2,
            ),
            RuntimeError("extraction failed"),
        ],
    ):
        batch = pipeline.run()

    assert batch.total == 2
    assert batch.processed == 1
    assert batch.failed == 1
    assert batch.errors[0].object_key == "source/2026/06/15/bad.pdf"
