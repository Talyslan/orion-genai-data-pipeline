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

    # Fonte local para ingestão de arquivos locais
    data_source_dir: str = "./prompts"
    data_source_extensions: str = ".txt,.md"

    # Transformação
    chunk_size: int = 1200
    chunk_overlap: int = 200
    cleaner_strip_nav: bool = True
    cleaner_max_blank_lines: int = 2
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32

    # Persistência Ouro
    postgres_url: str = "postgresql://orion:orion@localhost:5432/orion"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "document_embeddings"

    @property
    def extension_list(self) -> list[str]:
        return [
            ext.strip() for ext in self.data_source_extensions.split(",") if ext.strip()
        ]


settings = Settings()
