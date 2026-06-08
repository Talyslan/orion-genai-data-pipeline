from pydantic import BaseModel

from pipeline.shared.schemas.ingestion_result import IngestionResult


class BatchIngestionError(BaseModel):
    source_path: str
    error: str


class BatchIngestionResult(BaseModel):
    total_files: int
    succeeded: int
    failed: int
    results: list[IngestionResult]
    errors: list[BatchIngestionError]
