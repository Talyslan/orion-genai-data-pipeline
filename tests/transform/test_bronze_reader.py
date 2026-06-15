from unittest.mock import Mock

import fitz

from pipeline.transform.bronze_reader import BronzeReader, parse_front_matter


def test_parse_front_matter_extracts_metadata_and_body(
    fixtures_dir,
) -> None:
    raw = (fixtures_dir / "sample-bronze.md").read_text(encoding="utf-8")

    metadata, body = parse_front_matter(raw)

    assert metadata["source_path"] == "/abs/path/sample-prompt.txt"
    assert metadata["file_name"] == "sample-prompt.txt"
    assert "# sample-prompt" in body
    assert "Conteúdo de teste" in body


def test_fetch_object_parses_bronze_markdown(fixtures_dir) -> None:
    raw = (fixtures_dir / "sample-bronze.md").read_text(encoding="utf-8")
    mock_client = Mock()
    mock_stat = Mock(content_type="text/markdown")
    mock_response = Mock()
    mock_response.read.return_value = raw.encode("utf-8")
    mock_client.stat_object.return_value = mock_stat
    mock_client.get_object.return_value = mock_response

    reader = BronzeReader(client=mock_client)
    bronze_obj = reader.fetch_object("source/2026/06/08/sample-prompt.md")

    assert bronze_obj.object_key == "source/2026/06/08/sample-prompt.md"
    assert bronze_obj.source_path == "/abs/path/sample-prompt.txt"
    assert bronze_obj.file_name == "sample-prompt.txt"
    assert bronze_obj.is_pdf is False
    assert "Conteúdo de teste" in bronze_obj.body


def test_fetch_object_returns_pdf_bytes(tmp_path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "PDF bronze object")
    document.save(pdf_path)
    document.close()
    pdf_bytes = pdf_path.read_bytes()

    mock_client = Mock()
    mock_stat = Mock(content_type="application/pdf")
    mock_response = Mock()
    mock_response.read.return_value = pdf_bytes
    mock_client.stat_object.return_value = mock_stat
    mock_client.get_object.return_value = mock_response

    reader = BronzeReader(client=mock_client)
    bronze_obj = reader.fetch_object("source/2026/06/15/wellarchitected-framework.pdf")

    assert bronze_obj.is_pdf is True
    assert bronze_obj.raw_bytes == pdf_bytes
    assert bronze_obj.file_name == "wellarchitected-framework.pdf"
    assert bronze_obj.content_type == "application/pdf"


def test_list_objects_returns_sorted_keys() -> None:
    obj_a = Mock(object_name="source/2026/06/08/a.md")
    obj_b = Mock(object_name="source/2026/06/08/b.md")
    mock_client = Mock()
    mock_client.list_objects.return_value = [obj_b, obj_a]

    reader = BronzeReader(client=mock_client)
    keys = reader.list_objects("source/")

    assert keys == ["source/2026/06/08/a.md", "source/2026/06/08/b.md"]
