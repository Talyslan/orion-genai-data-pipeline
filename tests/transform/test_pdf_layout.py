import fitz

from pipeline.transform.pdf_layout import _ordered_text_blocks, table_to_markdown


def test_table_to_markdown() -> None:
    markdown = table_to_markdown([["Name", "Value"], ["A", "1"], ["B", "2"]])

    assert "| Name | Value |" in markdown
    assert "| --- | --- |" in markdown
    assert "| A | 1 |" in markdown


def test_blocks_sorted_by_position() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 200), "Second block")
    page.insert_text((72, 72), "First block")

    ordered = _ordered_text_blocks(page)
    document.close()

    assert ordered.index("First block") < ordered.index("Second block")
