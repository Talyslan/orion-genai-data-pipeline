"""API layer settings for the quarta entrega HTTP service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    allow_optional_corpus: bool = False
    corpus_strict_hash: bool = True
    pdf_max_upload_bytes: int = 80 * 1024 * 1024


api_settings = ApiSettings()
