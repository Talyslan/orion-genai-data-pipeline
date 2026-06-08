from uuid import UUID

from pydantic import BaseModel


class ChunkEmbedding(BaseModel):
    chunk_id: UUID
    vector: list[float]
    model: str = "BAAI/bge-m3"
