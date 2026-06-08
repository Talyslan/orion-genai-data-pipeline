"""Qdrant persistence for chunk embeddings."""

import logging
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from pipeline.shared.config import settings
from pipeline.shared.schemas.chunk_embedding import ChunkEmbedding

logger = logging.getLogger(__name__)

SERVICE = "qdrant"
EMBEDDING_DIMENSION = 1024


class QdrantStore:
    """Stores embeddings and trace payloads in Qdrant."""

    def __init__(
        self,
        client: QdrantClient | None = None,
        collection: str | None = None,
    ) -> None:
        self._client = client or QdrantClient(url=settings.qdrant_url)
        self._collection = collection or settings.qdrant_collection

    def ensure_collection(self) -> None:
        """Create the embeddings collection when it does not exist."""
        collections = {item.name for item in self._client.get_collections().collections}
        if self._collection in collections:
            return

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        logger.info(
            "Qdrant collection created",
            extra={"service": SERVICE, "collection": self._collection},
        )

    def upsert_embeddings(
        self,
        embeddings: list[ChunkEmbedding],
        payloads: list[dict],
    ) -> None:
        """Upsert vectors with trace payloads."""
        if not embeddings:
            return

        if len(embeddings) != len(payloads):
            msg = "embeddings and payloads must have the same length"
            raise ValueError(msg)

        self.ensure_collection()
        points = [
            PointStruct(
                id=str(embedding.chunk_id),
                vector=embedding.vector,
                payload=payload,
            )
            for embedding, payload in zip(embeddings, payloads, strict=True)
        ]
        self._client.upsert(collection_name=self._collection, points=points)

        logger.info(
            "Embeddings upserted",
            extra={
                "service": SERVICE,
                "collection": self._collection,
                "count": len(points),
            },
        )

    def get_payload(self, chunk_id: UUID) -> dict | None:
        """Retrieve the payload for a chunk id."""
        points = self._client.retrieve(
            collection_name=self._collection,
            ids=[str(chunk_id)],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None
        return points[0].payload or {}
