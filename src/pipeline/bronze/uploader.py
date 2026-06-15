"""MinIO client and Bronze layer object uploads."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from minio import Minio

from pipeline.shared.config import settings

logger = logging.getLogger(__name__)


class BronzeUploader:
    """Uploads local files to the MinIO Bronze layer."""

    def __init__(self, client: Minio | None = None, bucket: str | None = None) -> None:
        self._client = client or self._create_client()
        self._bucket = bucket or settings.minio_bucket

    def _create_client(self) -> Minio:
        return Minio(
            settings.minio_url,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self) -> None:
        """Create the Bronze bucket when it does not exist."""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def build_object_key(
        self,
        local_path: Path,
        uploaded_at: datetime | None = None,
        file_stem: str | None = None,
        file_extension: str | None = None,
    ) -> str:
        """Build the MinIO object key from the local file name and upload date."""
        timestamp = uploaded_at or datetime.now(UTC)
        date_prefix = timestamp.strftime("%Y/%m/%d")
        stem = file_stem or local_path.stem
        extension = file_extension or local_path.suffix or ".md"
        if not extension.startswith("."):
            extension = f".{extension}"
        return f"source/{date_prefix}/{stem}{extension}"

    def upload_file(
        self,
        local_path: Path,
        content_type: str = "text/markdown",
        file_stem: str | None = None,
        file_extension: str | None = None,
    ) -> str:
        """Upload a local file to MinIO Bronze and return the object key."""
        resolved_path = local_path.resolve()
        self.ensure_bucket()

        object_key = self.build_object_key(
            resolved_path,
            file_stem=file_stem,
            file_extension=file_extension,
        )
        file_size = resolved_path.stat().st_size

        self._client.fput_object(
            self._bucket,
            object_key,
            str(resolved_path),
            content_type=content_type,
        )
        self._client.stat_object(self._bucket, object_key)

        logger.info(
            "File uploaded to MinIO | bucket=%s object_key=%s size=%s",
            self._bucket,
            object_key,
            file_size,
        )

        return object_key


def upload_file(
    local_path: Path,
    content_type: str = "text/markdown",
    file_stem: str | None = None,
    file_extension: str | None = None,
) -> str:
    """Upload a local file using the default Bronze uploader."""
    return BronzeUploader().upload_file(
        local_path,
        content_type=content_type,
        file_stem=file_stem,
        file_extension=file_extension,
    )
