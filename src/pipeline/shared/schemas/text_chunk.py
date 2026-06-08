from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
