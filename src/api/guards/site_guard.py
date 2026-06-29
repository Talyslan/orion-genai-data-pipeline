"""AWS domain allowlist validation for POST /api/site."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from api.catalog import build_site_help_entries
from api.config import api_settings


@dataclass(frozen=True)
class SiteRejectedError(Exception):
    error_code: str
    http_status: int
    message: str
    help: dict

    def __str__(self) -> str:
        return self.message


def validate_site_url(url: str) -> str:
    """Validate and return a normalized AWS documentation URL."""
    cleaned = url.strip()
    if not cleaned:
        raise _reject(
            error_code="invalid_url",
            http_status=422,
            message="A URL não pode ser vazia.",
            url=url,
        )

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise _reject(
            error_code="invalid_url",
            http_status=422,
            message="A URL deve usar o esquema http ou https.",
            url=cleaned,
        )

    if not parsed.netloc:
        raise _reject(
            error_code="invalid_url",
            http_status=422,
            message="A URL informada é inválida.",
            url=cleaned,
        )

    if parsed.netloc not in api_settings.allowed_site_domain_list:
        raise _reject(
            error_code="site_domain_not_allowed",
            http_status=403,
            message=(f"A URL '{cleaned}' não está em um domínio AWS aceito."),
            url=cleaned,
        )

    return cleaned


def validate_site_urls(urls: list[str]) -> list[str]:
    """Validate a batch of site URLs."""
    return [validate_site_url(url) for url in urls]


def site_help_payload(
    *,
    error_code: str,
    url: str | None = None,
) -> dict:
    """Build a Portuguese help block for site-related errors."""
    domains_label = _allowed_domains_label()
    base = {
        "summary": (f"POST /api/site aceita apenas páginas em {domains_label}."),
        "steps": [
            "Consulte GET /api/site/help — campo sites lista URLs recomendadas.",
            (
                "Use páginas HTML complementares aos PDFs AWS "
                "(ex.: doc_page do manifest)."
            ),
            (
                "Exemplo: "
                "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"
            ),
        ],
        "discover": {"help": "/api/site/help"},
        "allowed_domains": list(api_settings.allowed_site_domain_list),
    }

    if error_code == "invalid_url":
        base["summary"] = "A URL informada não é válida para o pipeline."
        base["steps"] = [
            "Informe uma URL completa com http ou https.",
            "Consulte GET /api/site/help para exemplos de URLs aceitas.",
        ]

    if url:
        base["url"] = url

    return base


def build_site_help_response(
    *,
    pdf_manifest_path: str | None = None,
    sites_manifest_path: str | None = None,
) -> dict:
    """Build the GET /api/site/help payload."""
    sites = build_site_help_entries(
        pdf_manifest_path=pdf_manifest_path,
        sites_manifest_path=sites_manifest_path,
    )

    domains_label = _allowed_domains_label()
    return {
        "policy": "aws-domains-only",
        "summary": (f"Aceita URLs em {domains_label}. O pipeline faz o scrape."),
        "corpus": "aws-well-architected-sites",
        "message": (
            "POST /api/site aceita apenas os domínios listados em allowed_domains."
        ),
        "allowed_domains": list(api_settings.allowed_site_domain_list),
        "flow": {
            "step_1": "Leia sites abaixo — URLs recomendadas do corpus",
            "step_2": "POST /api/site com url ou urls (batch)",
            "step_3": "Resposta imediata: accepted ou rejected",
            "step_4": "GET /api/jobs/{job_id} — monitorar um job",
            "step_5": "GET /api/jobs — listar jobs (overview, filtros)",
        },
        "sites": sites,
        "usage": {
            "submit": "POST /api/site",
            "monitor_one": "GET /api/jobs/{job_id}",
            "monitor_list": "GET /api/jobs",
        },
        "examples": {
            "help": "curl -s http://localhost:8000/api/site/help | jq .",
            "single": (
                "curl -s -X POST http://localhost:8000/api/site "
                "-H 'Content-Type: application/json' "
                '-d \'{"url":'
                '"https://docs.aws.amazon.com/wellarchitected/latest/'
                "framework/welcome.html\"}' | jq ."
            ),
            "batch": (
                "curl -s -X POST http://localhost:8000/api/site "
                "-H 'Content-Type: application/json' "
                '-d \'{"urls":["https://docs.aws.amazon.com/..."]}\' | jq .'
            ),
            "poll": "curl -s http://localhost:8000/api/jobs/<job_id> | jq .",
            "list_jobs": (
                "curl -s 'http://localhost:8000/api/jobs?type=site&limit=20' | jq ."
            ),
        },
        "links": {"jobs": "/api/jobs", "pdf_help": "/api/pdf/help"},
    }


def _allowed_domains_label() -> str:
    domains = api_settings.allowed_site_domain_list
    if len(domains) == 1:
        return domains[0]
    return " e ".join((", ".join(domains[:-1]), domains[-1]))


def _reject(
    *,
    error_code: str,
    http_status: int,
    message: str,
    url: str | None,
) -> SiteRejectedError:
    return SiteRejectedError(
        error_code=error_code,
        http_status=http_status,
        message=message,
        help=site_help_payload(error_code=error_code, url=url),
    )
