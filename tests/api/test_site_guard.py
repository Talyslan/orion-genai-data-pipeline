from __future__ import annotations

import pytest

from api.guards.site_guard import (
    SiteRejectedError,
    build_site_help_response,
    validate_site_url,
    validate_site_urls,
)

VALID_URL = "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html"


def test_validate_site_url_accepts_aws_docs_domain() -> None:
    assert validate_site_url(VALID_URL) == VALID_URL


def test_validate_site_url_accepts_aws_amazon_domain() -> None:
    url = "https://aws.amazon.com/whitepapers/"
    assert validate_site_url(url) == url


def test_validate_site_url_rejects_external_domain() -> None:
    with pytest.raises(SiteRejectedError) as exc_info:
        validate_site_url("https://example.com/page")

    error = exc_info.value
    assert error.http_status == 403
    assert error.error_code == "site_domain_not_allowed"
    assert "steps" in error.help
    assert error.help["allowed_domains"] == [
        "docs.aws.amazon.com",
        "aws.amazon.com",
    ]


def test_validate_site_url_rejects_amazonaws_subdomain() -> None:
    with pytest.raises(SiteRejectedError) as exc_info:
        validate_site_url("https://s3.amazonaws.com/bucket/object")

    assert exc_info.value.error_code == "site_domain_not_allowed"


def test_validate_site_url_rejects_empty_url() -> None:
    with pytest.raises(SiteRejectedError) as exc_info:
        validate_site_url("   ")

    assert exc_info.value.error_code == "invalid_url"
    assert exc_info.value.http_status == 422


def test_validate_site_url_rejects_invalid_scheme() -> None:
    with pytest.raises(SiteRejectedError) as exc_info:
        validate_site_url("ftp://docs.aws.amazon.com/page")

    assert exc_info.value.error_code == "invalid_url"


def test_validate_site_urls_validates_batch() -> None:
    urls = [
        VALID_URL,
        "https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html",
    ]

    assert validate_site_urls(urls) == urls


def test_build_site_help_response_includes_allowed_domains() -> None:
    payload = build_site_help_response()

    assert payload["policy"] == "aws-domains-only"
    assert "docs.aws.amazon.com" in payload["allowed_domains"]
    assert isinstance(payload["sites"], list)
    assert len(payload["sites"]) >= 6
