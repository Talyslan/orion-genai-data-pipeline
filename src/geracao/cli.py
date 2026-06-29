"""CLI for the Geração app — `orion-geracao run --mode ...`."""

from __future__ import annotations

import argparse
import logging
import sys

from geracao.client import GeracaoClient
from geracao.config import geracao_settings
from geracao.orchestrator import run_mode

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        summary = run_mode(
            args.mode,
            document_id=args.document_id,
            url=args.url,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        logger.debug("run failed", exc_info=True)
        return 1

    print(f"Mode: {summary.mode}")
    print(f"Triggered: {len(summary.triggered)}")
    print(f"Rejected: {len(summary.rejected)}")
    print(f"Completed/skipped: {summary.completed_count}")
    print(f"Failed: {summary.failed_count}")

    for item in summary.triggered:
        print(f"  ENQUEUED {item.job_type} {item.source} -> {item.job_id}")

    for item in summary.rejected:
        print(
            f"  REJECTED {item.get('source', '?')}: "
            f"{item.get('message', item.get('error', 'unknown'))}",
            file=sys.stderr,
        )

    for item in summary.results:
        job_id = item.get("job_id", "?")
        status = item.get("status", "?")
        detail = item.get("message") or item.get("error") or ""
        suffix = f" — {detail}" if detail else ""
        print(f"  JOB {job_id}: {status}{suffix}")

    if summary.rejected or summary.failed_count:
        return 1
    if summary.mode != "single" and not summary.triggered:
        return 1
    return 0


def _cmd_health(_args: argparse.Namespace) -> int:
    try:
        with GeracaoClient() as client:
            payload = client.fetch_health()
    except Exception as exc:
        print(f"Error: pipeline API unavailable: {exc}", file=sys.stderr)
        return 1

    print(f"Pipeline API status: {payload.get('status', 'unknown')}")
    return 0 if payload.get("status") == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orion-geracao")
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Dispara ingestão via Pipeline API")
    run_parser.add_argument(
        "--mode",
        required=True,
        choices=["corpus", "site", "all", "single"],
        help="corpus=6 PDFs | site=URLs AWS | all=ambos | single=um item",
    )
    run_parser.add_argument(
        "--document-id",
        help="Modo single: document_id do manifest PDF",
    )
    run_parser.add_argument(
        "--url",
        help="Modo single: URL AWS allowlisted",
    )
    run_parser.set_defaults(func=_cmd_run)

    health_parser = subparsers.add_parser(
        "health",
        help="Verifica GET /api/health da Pipeline API",
    )
    health_parser.set_defaults(func=_cmd_health)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    print(f"Pipeline API: {geracao_settings.api_base_url}")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
