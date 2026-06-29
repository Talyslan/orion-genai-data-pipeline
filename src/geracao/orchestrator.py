"""Orchestration modes for corpus, site, all and single collection."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from geracao.client import GeracaoClient, GeracaoRejectedError
from geracao.config import REQUIRED_PDF_DOCUMENT_IDS, GeracaoSettings, geracao_settings

logger = logging.getLogger(__name__)

RunMode = Literal["corpus", "site", "all", "single"]
TERMINAL_STATUSES = frozenset({"completed", "skipped", "failed"})


@dataclass
class TriggeredJob:
    job_id: str
    job_type: str
    source: str


@dataclass
class RunSummary:
    mode: RunMode
    triggered: list[TriggeredJob] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)

    @property
    def failed_count(self) -> int:
        return sum(1 for item in self.results if item.get("status") == "failed")

    @property
    def completed_count(self) -> int:
        return sum(
            1 for item in self.results if item.get("status") in {"completed", "skipped"}
        )


def required_pdf_document_ids(client: GeracaoClient) -> list[str]:
    help_payload = client.fetch_pdf_help()
    documents = help_payload.get("documents", [])
    required_ids = [
        str(item["id"]) for item in documents if item.get("required") and item.get("id")
    ]
    if required_ids:
        return required_ids
    return list(REQUIRED_PDF_DOCUMENT_IDS)


def resolve_site_urls(client: GeracaoClient, settings: GeracaoSettings) -> list[str]:
    if settings.configured_site_urls:
        return list(settings.configured_site_urls)

    help_payload = client.fetch_site_help()
    sites = help_payload.get("sites", [])
    urls = [
        str(item["url"]) for item in sites if item.get("required") and item.get("url")
    ]
    if not urls:
        msg = "Nenhuma URL de site encontrada. Configure GERACAO_SITE_URLS."
        raise ValueError(msg)
    return urls


def run_mode(
    mode: RunMode,
    *,
    client: GeracaoClient | None = None,
    settings: GeracaoSettings | None = None,
    document_id: str | None = None,
    url: str | None = None,
) -> RunSummary:
    resolved_settings = settings or geracao_settings
    owns_client = client is None
    active_client = client or GeracaoClient(
        timeout=resolved_settings.request_timeout_seconds,
    )

    try:
        if mode == "corpus":
            return _run_corpus(active_client, resolved_settings)
        if mode == "site":
            return _run_site(active_client, resolved_settings)
        if mode == "all":
            corpus_summary = _run_corpus(active_client, resolved_settings)
            site_summary = _run_site(active_client, resolved_settings)
            return _merge_summaries("all", corpus_summary, site_summary)
        if mode == "single":
            return _run_single(
                active_client,
                resolved_settings,
                document_id=document_id,
                url=url,
            )
        msg = f"Modo inválido: {mode}"
        raise ValueError(msg)
    finally:
        if owns_client:
            active_client.close()


def _run_corpus(client: GeracaoClient, settings: GeracaoSettings) -> RunSummary:
    summary = RunSummary(mode="corpus")
    job_ids: list[str] = []

    for doc_id in required_pdf_document_ids(client):
        try:
            accepted = client.trigger_pdf(doc_id)
        except GeracaoRejectedError as exc:
            summary.rejected.append({"source": doc_id, **exc.payload})
            continue
        summary.triggered.append(
            TriggeredJob(job_id=accepted["job_id"], job_type="pdf", source=doc_id),
        )
        job_ids.append(accepted["job_id"])

    summary.results = wait_for_jobs(client, job_ids, settings)
    return summary


def _run_site(client: GeracaoClient, settings: GeracaoSettings) -> RunSummary:
    summary = RunSummary(mode="site")
    urls = resolve_site_urls(client, settings)
    job_ids: list[str] = []

    if len(urls) == 1:
        job_id = _submit_site(client, summary, urls[0])
        if job_id:
            job_ids.append(job_id)
    else:
        try:
            accepted = client.trigger_sites(urls)
            for item in accepted.get("jobs", []):
                summary.triggered.append(
                    TriggeredJob(
                        job_id=item["job_id"],
                        job_type="site",
                        source=str(item.get("input", {}).get("url", "")),
                    ),
                )
                job_ids.append(item["job_id"])
        except GeracaoRejectedError as exc:
            summary.rejected.append({"source": "batch", **exc.payload})

    summary.results = wait_for_jobs(client, job_ids, settings)
    return summary


def _submit_site(
    client: GeracaoClient,
    summary: RunSummary,
    url: str,
) -> str | None:
    try:
        accepted = client.trigger_site(url)
    except GeracaoRejectedError as exc:
        summary.rejected.append({"source": url, **exc.payload})
        return None
    summary.triggered.append(
        TriggeredJob(job_id=accepted["job_id"], job_type="site", source=url),
    )
    return accepted["job_id"]


def _run_single(
    client: GeracaoClient,
    settings: GeracaoSettings,
    *,
    document_id: str | None,
    url: str | None,
) -> RunSummary:
    has_doc = bool(document_id and document_id.strip())
    has_url = bool(url and url.strip())
    if has_doc == has_url:
        msg = "Modo single exige --document-id ou --url (exclusivo)."
        raise ValueError(msg)

    summary = RunSummary(mode="single")
    job_id: str | None = None

    if has_doc:
        doc_id = document_id.strip()  # type: ignore[union-attr]
        try:
            accepted = client.trigger_pdf(doc_id)
        except GeracaoRejectedError as exc:
            summary.rejected.append({"source": doc_id, **exc.payload})
            return summary
        job_id = accepted["job_id"]
        summary.triggered.append(
            TriggeredJob(job_id=job_id, job_type="pdf", source=doc_id),
        )
    else:
        site_url = url.strip()  # type: ignore[union-attr]
        job_id = _submit_site(client, summary, site_url)

    if job_id:
        summary.results = wait_for_jobs(client, [job_id], settings)
    return summary


def wait_for_jobs(
    client: GeracaoClient,
    job_ids: list[str],
    settings: GeracaoSettings,
) -> list[dict[str, Any]]:
    if not job_ids:
        return []

    pending = set(job_ids)
    results: dict[str, dict[str, Any]] = {}
    deadline = time.monotonic() + settings.job_timeout_seconds

    while pending and time.monotonic() < deadline:
        for job_id in list(pending):
            payload = client.poll_job(job_id)
            status = payload.get("status")
            if status in TERMINAL_STATUSES or status == "not_found":
                results[job_id] = payload
                pending.discard(job_id)
                logger.info(
                    "Job finished",
                    extra={"job_id": job_id, "status": status},
                )
        if pending:
            time.sleep(settings.poll_interval_seconds)

    for job_id in pending:
        results[job_id] = {
            "job_id": job_id,
            "status": "timeout",
            "message": "Timeout aguardando conclusão do job.",
        }

    return [results[job_id] for job_id in job_ids if job_id in results]


def _merge_summaries(mode: RunMode, *summaries: RunSummary) -> RunSummary:
    merged = RunSummary(mode=mode)
    for item in summaries:
        merged.triggered.extend(item.triggered)
        merged.results.extend(item.results)
        merged.rejected.extend(item.rejected)
    return merged
