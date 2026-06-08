from unittest.mock import Mock
from uuid import uuid4

from pipeline.shared.schemas.chunk_embedding import ChunkEmbedding
from pipeline.storage.qdrant_store import QdrantStore


def test_ensure_collection_creates_when_missing() -> None:
    mock_client = Mock()
    mock_client.get_collections.return_value.collections = []

    store = QdrantStore(client=mock_client, collection="document_embeddings")
    store.ensure_collection()

    mock_client.create_collection.assert_called_once()


def test_ensure_collection_skips_when_exists() -> None:
    mock_client = Mock()
    collection = Mock()
    collection.name = "document_embeddings"
    mock_client.get_collections.return_value.collections = [collection]

    store = QdrantStore(client=mock_client, collection="document_embeddings")
    store.ensure_collection()

    mock_client.create_collection.assert_not_called()


def test_upsert_embeddings_sends_points() -> None:
    chunk_id = uuid4()
    mock_client = Mock()
    collection = Mock(name="document_embeddings")
    mock_client.get_collections.return_value.collections = [collection]

    store = QdrantStore(client=mock_client, collection="document_embeddings")
    embeddings = [ChunkEmbedding(chunk_id=chunk_id, vector=[0.1] * 1024)]
    payloads = [{"chunk_id": str(chunk_id), "chunk_index": 0}]

    store.upsert_embeddings(embeddings, payloads)

    mock_client.upsert.assert_called_once()
    points = mock_client.upsert.call_args.kwargs["points"]
    assert points[0].id == str(chunk_id)
