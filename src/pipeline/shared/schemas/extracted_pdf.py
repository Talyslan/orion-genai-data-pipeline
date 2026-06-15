from pydantic import BaseModel, Field


class ExtractedPdf(BaseModel):
    markdown: str
    page_count: int
    tables_count: int = 0
    figures_count: int = 0
    pages_native: int = 0
    pages_ocr: int = 0
    methods_used: list[str] = Field(default_factory=list)
