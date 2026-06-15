"""PDF-specific text cleanup before the general cleaner."""

import re

_FIGURE_PLACEHOLDER_RE = re.compile(
    r"!\[figure page \d+ #\d+\]\([^)]+\)",
    re.IGNORECASE,
)
_PAGE_NUMBER_LINE_RE = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)
_HYPHENATED_LINE_BREAK_RE = re.compile(r"(\w+)-\n(\w+)", re.UNICODE)
_BROKEN_TABLE_LINE_RE = re.compile(r"^\|\s*$", re.MULTILINE)


def post_clean_pdf_text(text: str) -> str:
    """Normalize PDF extraction artifacts while preserving figure placeholders."""
    placeholders: dict[str, str] = {}

    def _stash_placeholder(match: re.Match[str]) -> str:
        token = f"__FIGURE_{len(placeholders)}__"
        placeholders[token] = match.group(0)
        return token

    protected = _FIGURE_PLACEHOLDER_RE.sub(_stash_placeholder, text)
    protected = _HYPHENATED_LINE_BREAK_RE.sub(r"\1\2", protected)
    protected = _PAGE_NUMBER_LINE_RE.sub("", protected)
    protected = _BROKEN_TABLE_LINE_RE.sub("", protected)
    protected = re.sub(r"\n{3,}", "\n\n", protected)

    for token, value in placeholders.items():
        protected = protected.replace(token, value)

    return protected.strip()
