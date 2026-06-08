from uuid import UUID

from pydantic import BaseModel


class TransformResult(BaseModel):
    object_key: str
    document_id: UUID | None = None
    skipped: bool = False
    chunks_count: int = 0
    embeddings_count: int = 0


class BatchTransformError(BaseModel):
    object_key: str
    error: str


class BatchTransformResult(BaseModel):
    total: int
    processed: int
    skipped: int
    failed: int
    results: list[TransformResult]
    errors: list[BatchTransformError]
