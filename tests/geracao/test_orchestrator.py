from __future__ import annotations

from geracao.orchestrator import required_pdf_document_ids, resolve_site_urls


class FakeClient:
    def __init__(self, pdf_help: dict, site_help: dict) -> None:
        self.pdf_help = pdf_help
        self.site_help = site_help

    def fetch_pdf_help(self) -> dict:
        return self.pdf_help

    def fetch_site_help(self) -> dict:
        return self.site_help


def test_required_pdf_document_ids_from_help() -> None:
    client = FakeClient(
        pdf_help={
            "documents": [
                {"id": "a", "required": True},
                {"id": "b", "required": False},
                {"id": "c", "required": True},
            ],
        },
        site_help={},
    )

    assert required_pdf_document_ids(client) == ["a", "c"]  # type: ignore[arg-type]


def test_resolve_site_urls_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "GERACAO_SITE_URLS",
        "https://docs.aws.amazon.com/a,https://docs.aws.amazon.com/b",
    )
    from geracao.config import GeracaoSettings

    settings = GeracaoSettings()
    client = FakeClient(pdf_help={}, site_help={"sites": []})

    urls = resolve_site_urls(client, settings)  # type: ignore[arg-type]

    assert urls == [
        "https://docs.aws.amazon.com/a",
        "https://docs.aws.amazon.com/b",
    ]
