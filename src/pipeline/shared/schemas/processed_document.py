from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProcessedDocument(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_path: str
    file_name: str
    file_hash: str
    minio_object_key: str
    cleaned_content: str
    source_format: str | None = None
    extraction_metadata: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
