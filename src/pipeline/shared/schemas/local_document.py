from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class LocalDocument(BaseModel):
    source_path: str
    file_name: str
    title: str
    content: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "title cannot be empty"
            raise ValueError(msg)
        return stripped

    def to_markdown(self) -> str:
        """Serialize the local document to Markdown with YAML front matter."""
        return (
            f"---\n"
            f"source_path: {self.source_path}\n"
            f"file_name: {self.file_name}\n"
            f"ingested_at: {self.ingested_at.isoformat()}\n"
            f"---\n\n"
            f"# {self.title}\n\n"
            f"{self.content}"
        )
