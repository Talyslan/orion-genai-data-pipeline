"""List and fetch objects from the MinIO Bronze layer."""

import logging
from dataclasses import dataclass

from minio import Minio

from pipeline.shared.config import settings

logger = logging.getLogger(__name__)

SERVICE = "bronze_reader"


@dataclass
class BronzeObject:
    object_key: str
    source_path: str | None
    file_name: str | None
    body: str
    raw_content: str


def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    """Parse optional YAML-like front matter from a Markdown file."""
    if not raw.startswith("---"):
        return {}, raw

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw

    metadata: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()

    body = parts[2].lstrip("\n")
    return metadata, body


class BronzeReader:
    """Reads objects from the MinIO Bronze bucket."""

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

    def list_objects(self, prefix: str = "source/") -> list[str]:
        """List object keys under a prefix."""
        keys = [
            obj.object_name
            for obj in self._client.list_objects(
                self._bucket,
                prefix=prefix,
                recursive=True,
            )
            if obj.object_name
        ]
        logger.info(
            "Objects listed",
            extra={"service": SERVICE, "prefix": prefix, "count": len(keys)},
        )
        return sorted(keys)

    def fetch_object(self, object_key: str) -> BronzeObject:
        """Download and parse a Bronze object."""
        try:
            response = self._client.get_object(self._bucket, object_key)
        except Exception as exc:
            msg = f"Bronze object not found: {object_key}"
            raise FileNotFoundError(msg) from exc

        try:
            raw = response.read().decode("utf-8")
        finally:
            response.close()
            response.release_conn()

        metadata, body = parse_front_matter(raw)
        bronze_obj = BronzeObject(
            object_key=object_key,
            source_path=metadata.get("source_path"),
            file_name=metadata.get("file_name"),
            body=body,
            raw_content=raw,
        )

        logger.info(
            "Object fetched",
            extra={"service": SERVICE, "object_key": object_key},
        )
        return bronze_obj

    def fetch_metadata(self, object_key: str) -> dict:
        """Return MinIO stat metadata for an object."""
        stat = self._client.stat_object(self._bucket, object_key)
        return {
            "size": stat.size,
            "last_modified": stat.last_modified,
            "content_type": stat.content_type,
        }
