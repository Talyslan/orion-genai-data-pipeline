from uuid import UUID

from pydantic import BaseModel


class TraceResult(BaseModel):
    chunk_id: UUID
    chunk_index: int
    chunk_content: str
    document_id: UUID
    file_name: str
    source_path: str
    minio_object_key: str
    source_format: str | None = None
