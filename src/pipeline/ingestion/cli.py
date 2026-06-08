"""Command-line interface for ingestion tasks."""

import argparse
import sys
from pathlib import Path

from pipeline.ingestion.pipeline import (
    ingest_directory,
    run_local_ingestion,
)
from pipeline.shared.schemas.ingestion_result import IngestionResult


def _print_result(result: IngestionResult) -> None:
    print("Ingestion completed")
    print(f"  source_path: {result.source_path}")
    print(f"  local_path:  {result.local_path}")
    print(f"  minio_key:   {result.minio_object_key}")


def _cmd_ingest_file(args: argparse.Namespace) -> int:
    file_path = Path(args.file_path)
    if not file_path.is_file():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 2

    try:
        result = run_local_ingestion(file_path)
    except Exception as exc:
        print(f"Error: ingestion failed: {exc}", file=sys.stderr)
        return 1

    _print_result(result)
    return 0


def _cmd_ingest_dir(args: argparse.Namespace) -> int:
    source_dir = Path(args.dir) if args.dir else None

    try:
        batch = ingest_directory(source_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: batch ingestion failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Batch ingestion completed | total={batch.total_files} "
        f"succeeded={batch.succeeded} failed={batch.failed}"
    )

    for error in batch.errors:
        print(f"  FAILED: {error.source_path} — {error.error}", file=sys.stderr)

    return 1 if batch.failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orion ingestion CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_file = subparsers.add_parser(
        "ingest-file",
        help="Ingest a single local file into Bronze",
    )
    ingest_file.add_argument("file_path", help="Path to the local file")
    ingest_file.set_defaults(func=_cmd_ingest_file)

    ingest_dir = subparsers.add_parser(
        "ingest-dir",
        help="Ingest all matching files from a directory",
    )
    ingest_dir.add_argument(
        "--dir",
        help="Source directory (default: DATA_SOURCE_DIR from settings)",
    )
    ingest_dir.set_defaults(func=_cmd_ingest_dir)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
