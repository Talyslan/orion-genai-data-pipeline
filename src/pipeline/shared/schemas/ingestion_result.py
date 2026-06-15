from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, HttpUrl


class IngestionResult(BaseModel):
    source_path: str
    local_path: Path
    minio_object_key: str
    ingested_at: datetime
    url: HttpUrl | None = None
    source_format: str | None = None
    page_count: int | None = None
