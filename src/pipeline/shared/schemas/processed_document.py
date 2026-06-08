from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProcessedDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_path: str
    file_name: str
    file_hash: str
    minio_object_key: str
    cleaned_content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
