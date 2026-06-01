from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ScrapedPage(BaseModel):
    url: HttpUrl
    title: str
    content: str
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "title cannot be empty"
            raise ValueError(msg)
        return stripped

    def to_markdown(self) -> str:
        """Serialize the scraped page to Markdown for local persistence."""
        return (
            f"# {self.title}\n\n"
            f"**URL:** {self.url}\n"
            f"**Coletado em:** {self.scraped_at.isoformat()}\n\n"
            f"---\n\n"
            f"{self.content}"
        )
