from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, HttpUrl


class IngestionResult(BaseModel):
    url: HttpUrl
    local_path: Path
    minio_object_key: str
    scraped_at: datetime
