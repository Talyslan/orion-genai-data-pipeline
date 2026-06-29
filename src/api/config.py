"""API layer settings for the quarta entrega HTTP service."""

from functools import cached_property

from pydantic import field_validator
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
    site_manifest_path: str = "./sites/manifest.yaml"
    allowed_site_domains: str = "docs.aws.amazon.com,aws.amazon.com"
    job_ttl_seconds: int = 86400

    @field_validator("allowed_site_domains")
    @classmethod
    def validate_allowed_site_domains(cls, value: str) -> str:
        domains = [domain.strip() for domain in value.split(",") if domain.strip()]
        if not domains:
            msg = "ALLOWED_SITE_DOMAINS must list at least one domain"
            raise ValueError(msg)
        return ",".join(domains)

    @cached_property
    def allowed_site_domain_list(self) -> tuple[str, ...]:
        return tuple(
            domain.strip()
            for domain in self.allowed_site_domains.split(",")
            if domain.strip()
        )


api_settings = ApiSettings()
