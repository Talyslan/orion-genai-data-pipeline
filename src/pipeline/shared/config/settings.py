from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
