"""Content cleaning and HTML to Markdown conversion."""

import logging
import re
import unicodedata

import html2text
from bs4 import BeautifulSoup

from pipeline.shared.config import settings

logger = logging.getLogger(__name__)

SERVICE = "cleaner"

_HTML_TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")
_NAV_TAGS = ("nav", "footer", "header", "aside")


def _contains_html(text: str) -> bool:
    return bool(_HTML_TAG_RE.search(text))


def _remove_nav_elements(soup: BeautifulSoup) -> None:
    if not settings.cleaner_strip_nav:
        return
    for tag_name in _NAV_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()


def _html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    _remove_nav_elements(soup)

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0
    return converter.handle(str(soup))


def _collapse_blank_lines(text: str) -> str:
    max_lines = settings.cleaner_max_blank_lines
    pattern = rf"\n{{{max_lines + 2},}}"
    replacement = "\n" * (max_lines + 1)
    return re.sub(pattern, replacement, text)


def _deduplicate_paragraphs(text: str) -> str:
    paragraphs = text.split("\n\n")
    deduped: list[str] = []
    previous = None
    for paragraph in paragraphs:
        normalized = paragraph.strip()
        if normalized and normalized != previous:
            deduped.append(paragraph)
            previous = normalized
        elif not normalized:
            deduped.append(paragraph)
    return "\n\n".join(deduped)


def clean_content(raw: str) -> str:
    """Normalize content to clean Markdown."""
    text = unicodedata.normalize("NFC", raw)

    if _contains_html(text):
        text = _html_to_markdown(text)

    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = _deduplicate_paragraphs(text)
    text = _collapse_blank_lines(text)
    cleaned = text.strip()

    logger.info(
        "Content cleaned",
        extra={
            "service": SERVICE,
            "input_chars": len(raw),
            "output_chars": len(cleaned),
        },
    )
    return cleaned
