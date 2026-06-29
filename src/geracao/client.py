"""HTTP client for the Pipeline API (/api/*)."""

from __future__ import annotations

from typing import Any

import httpx

from geracao.config import geracao_settings


class GeracaoApiError(Exception):
    """Unexpected HTTP or transport error from the Pipeline API."""


class GeracaoRejectedError(GeracaoApiError):
    """Pipeline rejected the submission (403/404/413/503)."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(payload.get("message") or payload.get("error", "rejected"))


class GeracaoClient:
    """Client for POST /api/pdf, POST /api/site and GET /api/jobs."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        client: httpx.Client | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or geracao_settings.api_base_url).rstrip("/")
        self._timeout = timeout or geracao_settings.request_timeout_seconds
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self.base_url, timeout=self._timeout)
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> GeracaoClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def fetch_pdf_help(self) -> dict[str, Any]:
        return self._get_json("/pdf/help")

    def fetch_site_help(self) -> dict[str, Any]:
        return self._get_json("/site/help")

    def fetch_health(self) -> dict[str, Any]:
        return self._get_json("/health")

    def trigger_pdf(self, document_id: str) -> dict[str, Any]:
        response = self._get_client().post("/pdf", json={"document_id": document_id})
        return self._parse_submit_response(response)

    def trigger_site(self, url: str) -> dict[str, Any]:
        response = self._get_client().post("/site", json={"url": url})
        return self._parse_submit_response(response)

    def trigger_sites(self, urls: list[str]) -> dict[str, Any]:
        response = self._get_client().post("/site", json={"urls": urls})
        return self._parse_batch_response(response)

    def poll_job(self, job_id: str) -> dict[str, Any]:
        response = self._get_client().get(f"/jobs/{job_id}")
        if response.status_code == 404:
            return response.json()
        response.raise_for_status()
        return response.json()

    def _get_json(self, path: str) -> dict[str, Any]:
        response = self._get_client().get(path)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GeracaoApiError(str(exc)) from exc
        payload = response.json()
        if not isinstance(payload, dict):
            msg = f"Unexpected JSON payload from {path}"
            raise GeracaoApiError(msg)
        return payload

    def _parse_submit_response(self, response: httpx.Response) -> dict[str, Any]:
        payload = response.json()
        if response.status_code == 202 and payload.get("enqueued"):
            return payload
        if response.status_code in {403, 404, 413, 422, 503}:
            raise GeracaoRejectedError(payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GeracaoApiError(str(exc)) from exc
        return payload

    def _parse_batch_response(self, response: httpx.Response) -> dict[str, Any]:
        payload = response.json()
        if response.status_code == 202 and payload.get("enqueued"):
            return payload
        if response.status_code in {403, 422}:
            raise GeracaoRejectedError(payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GeracaoApiError(str(exc)) from exc
        return payload
