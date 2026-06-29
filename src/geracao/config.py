"""Settings for the Geração app."""

from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REQUIRED_PDF_DOCUMENT_IDS: tuple[str, ...] = (
    "wellarchitected-framework",
    "performance-efficiency-pillar",
    "reliability-pillar",
    "security-pillar",
    "sustainability-pillar",
    "microservices-on-aws",
)


class GeracaoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pipeline_api_url: str = Field(
        default="http://localhost:8000/api",
        validation_alias="PIPELINE_API_URL",
    )
    poll_interval_seconds: float = Field(
        default=5.0,
        validation_alias="GERACAO_POLL_INTERVAL_SECONDS",
    )
    job_timeout_seconds: float = Field(
        default=3600.0,
        validation_alias="GERACAO_JOB_TIMEOUT_SECONDS",
    )
    site_urls: str = Field(default="", validation_alias="GERACAO_SITE_URLS")
    request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="GERACAO_REQUEST_TIMEOUT_SECONDS",
    )

    @cached_property
    def api_base_url(self) -> str:
        return self.pipeline_api_url.rstrip("/")

    @cached_property
    def configured_site_urls(self) -> tuple[str, ...]:
        return tuple(url.strip() for url in self.site_urls.split(",") if url.strip())


geracao_settings = GeracaoSettings()
