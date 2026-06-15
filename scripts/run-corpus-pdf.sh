#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=== 1/5 Docker services ==="
docker compose up -d

echo "=== 2/5 PostgreSQL migration ==="
uv run python -m pipeline.transform.cli migrate

echo "=== 3/5 Corpus status ==="
uv run python -m pipeline.ingestion.cli corpus-status

echo "=== 4/5 Ingest PDFs from ./pdfs ==="
uv run python -m pipeline.ingestion.cli ingest-dir --dir ./pdfs

echo "=== 5/5 Transform Bronze → Ouro ==="
uv run python -m pipeline.transform.cli run

echo "Done. Verify with: bash scripts/verify-ouro.sh"
