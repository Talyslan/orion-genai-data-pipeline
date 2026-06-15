from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PDF_EXTRACTION_MODES = frozenset({"native", "structured", "unstructured"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # MinIO
    minio_url: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "bronze"
    minio_secure: bool = False

    # Ingestão
    scrape_url: str = "https://example.com"
    local_output_dir: str = "data/local"
    request_timeout_seconds: int = 30

    # Fonte local para ingestão de arquivos locais
    data_source_dir: str = "./pdfs"
    data_source_extensions: str = ".txt,.md,.pdf"

    # PDF — ingestão e extração (terceira entrega)
    pdf_extractor: str = "pymupdf"
    pdf_extraction_mode: str = "structured"
    pdf_max_pages: int = 0
    pdf_ocr_enabled: bool = True
    pdf_ocr_min_chars: int = 50
    pdf_ocr_lang: str = "eng+por"
    pdf_ocr_dpi: int = 200
    pdf_extract_tables: bool = True
    pdf_figure_placeholder: bool = True
    pdf_manifest_path: str = "./pdfs/manifest.yaml"
    pdf_download_dir: str = "./pdfs"
    pdf_download_skip_existing: bool = True
    pdf_download_timeout_seconds: int = 120

    # OCR — Tesseract (Windows: .venv/share/tesseract via scripts/setup-tesseract.sh)
    tesseract_cmd: str = ""
    tessdata_prefix: str = ""

    # Transformação
    chunk_size: int = 1200
    chunk_overlap: int = 200
    cleaner_strip_nav: bool = True
    cleaner_max_blank_lines: int = 2
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32

    # Persistência Ouro
    postgres_url: str = "postgresql://orion:orion@localhost:5433/orion"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "document_embeddings"

    @field_validator("pdf_extraction_mode")
    @classmethod
    def validate_pdf_extraction_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in PDF_EXTRACTION_MODES:
            allowed = ", ".join(sorted(PDF_EXTRACTION_MODES))
            msg = f"PDF_EXTRACTION_MODE must be one of: {allowed}"
            raise ValueError(msg)
        return normalized

    @field_validator("pdf_max_pages")
    @classmethod
    def validate_pdf_max_pages(cls, value: int) -> int:
        if value < 0:
            msg = "PDF_MAX_PAGES must be >= 0 (0 = no limit)"
            raise ValueError(msg)
        return value

    @field_validator("pdf_ocr_min_chars", "pdf_ocr_dpi")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value < 1:
            msg = "PDF OCR settings must be positive integers"
            raise ValueError(msg)
        return value

    @property
    def extension_list(self) -> list[str]:
        return [
            ext.strip() for ext in self.data_source_extensions.split(",") if ext.strip()
        ]

    @property
    def resolved_tesseract_cmd(self) -> str | None:
        """Return Tesseract executable path (explicit env or local venv install)."""
        if self.tesseract_cmd.strip():
            return self.tesseract_cmd.strip()

        local_exe = Path(".venv/share/tesseract/tesseract.exe")
        if local_exe.is_file():
            return str(local_exe.resolve())

        return None

    @property
    def resolved_tessdata_prefix(self) -> str | None:
        """Return tessdata directory for Tesseract."""
        if self.tessdata_prefix.strip():
            return self.tessdata_prefix.strip()

        local_tessdata = Path(".venv/share/tesseract/tessdata")
        if local_tessdata.is_dir():
            return str(local_tessdata.resolve())

        return None


settings = Settings()
