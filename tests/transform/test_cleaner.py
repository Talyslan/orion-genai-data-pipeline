from pipeline.transform.cleaner import clean_content


def test_clean_content_converts_html_and_removes_script(fixtures_dir) -> None:
    raw = (fixtures_dir / "sample.html").read_text(encoding="utf-8")

    cleaned = clean_content(raw)

    assert "<script>" not in cleaned
    assert "<nav>" not in cleaned
    assert "mundo" in cleaned


def test_clean_content_preserves_plain_text() -> None:
    raw = "Texto simples sem HTML."

    cleaned = clean_content(raw)

    assert cleaned == "Texto simples sem HTML."


def test_clean_content_collapses_excessive_blank_lines() -> None:
    raw = "Linha 1\n\n\n\n\nLinha 2"

    cleaned = clean_content(raw)

    assert "\n\n\n\n" not in cleaned
    assert "Linha 1" in cleaned
    assert "Linha 2" in cleaned
