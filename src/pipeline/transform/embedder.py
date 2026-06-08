"""Embedding generation with BGE-M3."""

import logging
from typing import TYPE_CHECKING

from pipeline.shared.config import settings
from pipeline.shared.schemas.chunk_embedding import ChunkEmbedding
from pipeline.shared.schemas.text_chunk import TextChunk

logger = logging.getLogger(__name__)

SERVICE = "embedder"

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_model: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        print(
            f"Loading embedding model {settings.embedding_model} "
            f"({settings.embedding_device})...",
            flush=True,
        )
        _model = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
        )
        print("Model loaded.", flush=True)
    return _model


class Embedder:
    """Generates dense embeddings for text chunks."""

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name or settings.embedding_model
        self._device = device or settings.embedding_device

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        if not texts:
            return []

        model = _get_model()
        print(f"Generating embeddings for {len(texts)} chunk(s)...", flush=True)
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=settings.embedding_batch_size,
            show_progress_bar=len(texts) > 1,
        )
        return [vector.tolist() for vector in vectors]

    def embed_chunks(self, chunks: list[TextChunk]) -> list[ChunkEmbedding]:
        """Generate embeddings for non-empty chunks."""
        eligible = [chunk for chunk in chunks if chunk.content.strip()]
        if not eligible:
            return []

        vectors = self.embed([chunk.content for chunk in eligible])
        embeddings = [
            ChunkEmbedding(
                chunk_id=chunk.id,
                vector=vector,
                model=self._model_name,
            )
            for chunk, vector in zip(eligible, vectors, strict=True)
        ]

        dimension = len(embeddings[0].vector) if embeddings else 0
        logger.info(
            "Embeddings generated",
            extra={
                "service": SERVICE,
                "count": len(embeddings),
                "model": self._model_name,
                "dimension": dimension,
            },
        )
        return embeddings
