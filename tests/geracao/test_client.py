from __future__ import annotations

import httpx
import pytest

from geracao.client import GeracaoClient, GeracaoRejectedError


@pytest.fixture
def api_base() -> str:
    return "http://pipeline.test/api"


def test_fetch_pdf_help(api_base: str) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"documents": [{"id": "wellarchitected-framework", "required": True}]},
        ),
    )
    client = httpx.Client(transport=transport, base_url=api_base)
    geracao = GeracaoClient(client=client)

    payload = geracao.fetch_pdf_help()

    assert payload["documents"][0]["id"] == "wellarchitected-framework"
    geracao.close()


def test_trigger_pdf_accepted(api_base: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pdf"
        assert request.method == "POST"
        return httpx.Response(
            202,
            json={
                "status": "accepted",
                "enqueued": True,
                "job_id": "job-1",
                "type": "pdf",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=api_base)
    geracao = GeracaoClient(client=client)

    payload = geracao.trigger_pdf("wellarchitected-framework")

    assert payload["job_id"] == "job-1"
    geracao.close()


def test_trigger_pdf_rejected(api_base: str) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            403,
            json={
                "status": "rejected",
                "enqueued": False,
                "error": "pdf_not_in_corpus",
                "message": "rejected",
            },
        ),
    )
    client = httpx.Client(transport=transport, base_url=api_base)
    geracao = GeracaoClient(client=client)

    with pytest.raises(GeracaoRejectedError):
        geracao.trigger_pdf("__invalid__")

    geracao.close()


def test_trigger_sites_batch(api_base: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/site"
        return httpx.Response(
            202,
            json={
                "status": "accepted",
                "enqueued": True,
                "jobs": [
                    {"job_id": "job-a", "type": "site", "input": {"url": "https://a"}},
                    {"job_id": "job-b", "type": "site", "input": {"url": "https://b"}},
                ],
                "total": 2,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url=api_base)
    geracao = GeracaoClient(client=client)

    payload = geracao.trigger_sites(["https://a", "https://b"])

    assert payload["total"] == 2
    assert len(payload["jobs"]) == 2
    geracao.close()


def test_poll_job(api_base: str) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "job_id": "job-1",
                "status": "completed",
                "result": {"chunks_count": 3},
            },
        ),
    )
    client = httpx.Client(transport=transport, base_url=api_base)
    geracao = GeracaoClient(client=client)

    payload = geracao.poll_job("job-1")

    assert payload["status"] == "completed"
    assert payload["result"]["chunks_count"] == 3
    geracao.close()
