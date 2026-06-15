from pipeline.transform.pdf_post_clean import post_clean_pdf_text


def test_post_clean_pdf_text_joins_hyphenated_line_breaks() -> None:
    raw = "optimiza-\nção de performance"

    cleaned = post_clean_pdf_text(raw)

    assert cleaned == "optimização de performance"


def test_post_clean_pdf_text_removes_page_number_lines() -> None:
    raw = "Introdução\n\n42\n\nConteúdo principal"

    cleaned = post_clean_pdf_text(raw)

    assert "42" not in cleaned.splitlines()
    assert "Conteúdo principal" in cleaned


def test_post_clean_pdf_text_preserves_figure_placeholder() -> None:
    placeholder = "![figure page 2 #1](diagram — conteúdo visual sem texto extraído)"
    raw = f"Texto\n\n{placeholder}\n\n42"

    cleaned = post_clean_pdf_text(raw)

    assert placeholder in cleaned
