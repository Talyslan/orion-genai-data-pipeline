"""MinIO client and Bronze layer object uploads."""

from pathlib import Path


def upload_file(local_path: Path, content_type: str = "text/markdown") -> str:
    """Upload a local file to MinIO Bronze and return the object key."""
    raise NotImplementedError
