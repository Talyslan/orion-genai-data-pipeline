from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PdfSourceFormat = Literal["pdf"]


class PdfDocument(BaseModel):
    source_path: str
    file_name: str
    title: str
    page_count: int
    source_format: PdfSourceFormat = "pdf"
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "title cannot be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("page_count")
    @classmethod
    def validate_page_count(cls, value: int) -> int:
        if value < 1:
            msg = "page_count must be at least 1"
            raise ValueError(msg)
        return value

    def to_markdown(self) -> str:
        """Serialize PDF metadata as Markdown with YAML front matter."""
        return (
            f"---\n"
            f"source_path: {self.source_path}\n"
            f"file_name: {self.file_name}\n"
            f"source_format: {self.source_format}\n"
            f"page_count: {self.page_count}\n"
            f"ingested_at: {self.ingested_at.isoformat()}\n"
            f"---\n\n"
            f"# {self.title}\n\n"
            f"PDF ingerido. Conteúdo original no Bronze; extração na transformação.\n"
        )
