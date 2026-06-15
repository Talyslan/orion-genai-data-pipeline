"""Command-line interface for ingestion tasks."""

import argparse
import sys
from pathlib import Path

from pipeline.ingestion.corpus import check_corpus
from pipeline.ingestion.corpus_download import download_corpus
from pipeline.ingestion.pipeline import (
    ingest_directory,
    run_local_ingestion,
)
from pipeline.shared.config import settings
from pipeline.shared.schemas.ingestion_result import IngestionResult


def _parse_extensions(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [ext.strip() for ext in raw.split(",") if ext.strip()]


def _print_no_files_hint(source_dir: Path, extensions: list[str]) -> None:
    from pipeline.ingestion.pipeline import _list_directory_files

    _, all_files = _list_directory_files(source_dir.resolve(), extensions)
    if not all_files:
        print(
            f"No files found in directory: {source_dir}",
            file=sys.stderr,
        )
        return

    skipped_suffixes = sorted({path.suffix for path in all_files if path.suffix})
    print(
        "No files matched the configured extensions.",
        file=sys.stderr,
    )
    print(f"  directory: {source_dir.resolve()}", file=sys.stderr)
    print(f"  extensions: {', '.join(extensions)}", file=sys.stderr)
    print(
        f"  files in directory: {len(all_files)} "
        f"with suffix(es): {', '.join(skipped_suffixes) or '(none)'}",
        file=sys.stderr,
    )
    if ".pdf" in skipped_suffixes and ".pdf" not in {
        ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions
    }:
        print(
            "  hint: add --extensions .pdf or set "
            "DATA_SOURCE_EXTENSIONS=.txt,.md,.pdf in .env",
            file=sys.stderr,
        )


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
    source_dir = Path(args.dir) if args.dir else Path(settings.data_source_dir)
    extensions = _parse_extensions(args.extensions)

    try:
        batch = ingest_directory(source_dir, extensions)
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

    if batch.total_files == 0:
        effective_extensions = extensions or settings.extension_list
        _print_no_files_hint(source_dir, effective_extensions)

    for result in batch.results:
        print(f"  OK: {result.source_path} (minio_key={result.minio_object_key})")

    for error in batch.errors:
        print(f"  FAILED: {error.source_path} — {error.error}", file=sys.stderr)

    return 1 if batch.failed else 0


def _cmd_corpus_status(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest) if args.manifest else None
    corpus_dir = Path(args.dir) if args.dir else None

    try:
        status = check_corpus(manifest_path, corpus_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: corpus check failed: {exc}", file=sys.stderr)
        return 1

    required = len(status.required_documents)
    missing = len(status.missing_required)

    print(f"Corpus status | dir={status.corpus_dir}")
    print(f"  manifest: {status.manifest_path}")
    print(
        f"  files: {status.valid_count}/{len(status.files)} valid "
        f"({status.present_count} present)"
    )
    print(f"  required ready: {required - missing}/{required}")

    for item in status.files:
        if item.valid_pdf:
            label = "OK"
        elif item.present:
            label = "INVALID"
        elif item.document.optional:
            label = "OPTIONAL"
        else:
            label = "MISSING"

        suffix = f" — {item.error}" if item.error else ""
        optional = " (optional)" if item.document.optional else ""
        print(f"  [{label}] {item.document.filename}{optional}{suffix}")

    if not status.is_ready:
        print(
            "Corpus incomplete — download missing PDFs (see pdfs/README.md)",
            file=sys.stderr,
        )
        return 1

    print("Corpus ready for ingestion.")
    return 0


def _cmd_download_corpus(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest) if args.manifest else None
    corpus_dir = Path(args.dir) if args.dir else None

    try:
        batch = download_corpus(
            manifest_path,
            corpus_dir,
            skip_existing=not args.force,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: download failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Download completed | dir={batch.corpus_dir} "
        f"downloaded={batch.downloaded} skipped={batch.skipped} "
        f"failed={batch.failed} no_url={batch.no_url}"
    )

    for item in batch.results:
        if item.status == "downloaded":
            print(f"  DOWNLOADED: {item.document.filename}")
        elif item.status == "skipped":
            print(f"  SKIPPED: {item.document.filename} (unchanged)")
        elif item.status == "no_url":
            print(f"  NO_URL: {item.document.filename} — {item.error}")
        else:
            print(
                f"  FAILED: {item.document.filename} — {item.error}",
                file=sys.stderr,
            )

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
    ingest_dir.add_argument(
        "--extensions",
        help="Comma-separated extensions to ingest (default: DATA_SOURCE_EXTENSIONS)",
    )
    ingest_dir.set_defaults(func=_cmd_ingest_dir)

    corpus_status = subparsers.add_parser(
        "corpus-status",
        help="Verify local PDF corpus against manifest.yaml",
    )
    corpus_status.add_argument(
        "--dir",
        help="Corpus directory (default: PDF_DOWNLOAD_DIR / DATA_SOURCE_DIR)",
    )
    corpus_status.add_argument(
        "--manifest",
        help="Manifest path (default: PDF_MANIFEST_PATH)",
    )
    corpus_status.set_defaults(func=_cmd_corpus_status)

    download_corpus_cmd = subparsers.add_parser(
        "download-corpus",
        help="Download PDFs listed in manifest.yaml",
    )
    download_corpus_cmd.add_argument(
        "--dir",
        help="Download directory (default: PDF_DOWNLOAD_DIR)",
    )
    download_corpus_cmd.add_argument(
        "--manifest",
        help="Manifest path (default: PDF_MANIFEST_PATH)",
    )
    download_corpus_cmd.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when local hash matches remote",
    )
    download_corpus_cmd.set_defaults(func=_cmd_download_corpus)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
