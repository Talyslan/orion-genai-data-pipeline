"""Command-line interface for transformation tasks."""

import argparse
import sys
from uuid import UUID

from pipeline.storage.postgres import PostgresStore, run_migration
from pipeline.transform.pipeline import run_transform, trace_vector


def _cmd_migrate(args: argparse.Namespace) -> int:
    try:
        if args.sql_file:
            run_migration(args.sql_file)
        else:
            PostgresStore().ensure_schema()
    except Exception as exc:
        print(f"Error: migration failed: {exc}", file=sys.stderr)
        return 1

    print("PostgreSQL migration completed")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        batch = run_transform(object_key=args.object_key, prefix=args.prefix)
    except Exception as exc:
        print(f"Error: transformation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Transform completed | total={batch.total} processed={batch.processed} "
        f"skipped={batch.skipped} failed={batch.failed}"
    )

    for result in batch.results:
        if result.skipped:
            print(f"  SKIPPED: {result.object_key} (document_id={result.document_id})")
        else:
            print(
                f"  OK: {result.object_key} "
                f"(chunks={result.chunks_count}, embeddings={result.embeddings_count})"
            )

    for error in batch.errors:
        print(f"  FAILED: {error.object_key} — {error.error}", file=sys.stderr)

    return 1 if batch.failed else 0


def _cmd_trace(args: argparse.Namespace) -> int:
    try:
        chunk_id = UUID(args.chunk_id)
        result = trace_vector(chunk_id)
    except (ValueError, LookupError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Trace result")
    print(f"  chunk_id:          {result.chunk_id}")
    print(f"  chunk_index:       {result.chunk_index}")
    print(f"  document_id:       {result.document_id}")
    print(f"  file_name:         {result.file_name}")
    print(f"  source_path:       {result.source_path}")
    print(f"  minio_object_key:  {result.minio_object_key}")
    print(f"  chunk_content:     {result.chunk_content[:120]}...")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orion transform CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_cmd = subparsers.add_parser(
        "migrate",
        help="Create PostgreSQL tables (no psql required)",
    )
    migrate_cmd.add_argument(
        "--sql-file",
        type=str,
        default=None,
        help="Optional SQL file (default: built-in schema)",
    )
    migrate_cmd.set_defaults(func=_cmd_migrate)

    run_cmd = subparsers.add_parser("run", help="Run Bronze transformation")
    run_cmd.add_argument(
        "--object-key",
        help="Transform a single MinIO object key",
    )
    run_cmd.add_argument(
        "--prefix",
        default="source/",
        help="Bronze prefix when processing all objects",
    )
    run_cmd.set_defaults(func=_cmd_run)

    trace_cmd = subparsers.add_parser("trace", help="Trace a vector/chunk id")
    trace_cmd.add_argument("chunk_id", help="Chunk UUID")
    trace_cmd.set_defaults(func=_cmd_trace)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
