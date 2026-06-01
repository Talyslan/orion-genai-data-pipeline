from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from pipeline.bronze.uploader import BronzeUploader, upload_file


def test_build_object_key_uses_utc_date_and_local_filename() -> None:
    uploader = BronzeUploader(client=Mock())
    local_path = Path("550e8400-e29b-41d4-a716-446655440000.md")
    uploaded_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    object_key = uploader.build_object_key(local_path, uploaded_at)

    assert object_key == "source/2026/06/01/550e8400-e29b-41d4-a716-446655440000.md"


def test_upload_file_calls_fput_object_and_stat_object(tmp_path: Path) -> None:
    mock_client = Mock()
    mock_client.bucket_exists.return_value = True
    uploader = BronzeUploader(client=mock_client)

    local_file = tmp_path / "550e8400-e29b-41d4-a716-446655440000.md"
    local_file.write_text("# Test", encoding="utf-8")

    object_key = uploader.upload_file(local_file)

    assert object_key.startswith("source/")
    assert object_key.endswith("550e8400-e29b-41d4-a716-446655440000.md")
    mock_client.fput_object.assert_called_once_with(
        "bronze",
        object_key,
        str(local_file.resolve()),
        content_type="text/markdown",
    )
    mock_client.stat_object.assert_called_once_with("bronze", object_key)


def test_upload_file_creates_bucket_when_missing(tmp_path: Path) -> None:
    mock_client = Mock()
    mock_client.bucket_exists.return_value = False
    uploader = BronzeUploader(client=mock_client)

    local_file = tmp_path / "550e8400-e29b-41d4-a716-446655440000.md"
    local_file.write_text("# Test", encoding="utf-8")

    uploader.upload_file(local_file)

    mock_client.make_bucket.assert_called_once_with("bronze")


@patch("pipeline.bronze.uploader.BronzeUploader")
def test_module_upload_file_delegates_to_bronze_uploader(
    mock_uploader_cls: Mock,
    tmp_path: Path,
) -> None:
    mock_instance = Mock()
    mock_instance.upload_file.return_value = "source/2026/06/01/file.md"
    mock_uploader_cls.return_value = mock_instance

    local_file = tmp_path / "test.md"
    local_file.write_text("# Test", encoding="utf-8")

    result = upload_file(local_file)

    mock_uploader_cls.assert_called_once_with()
    mock_instance.upload_file.assert_called_once_with(
        local_file,
        content_type="text/markdown",
    )
    assert result == "source/2026/06/01/file.md"
