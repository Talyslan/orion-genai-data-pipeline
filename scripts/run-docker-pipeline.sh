#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

PROFILE="${COMPOSE_PROFILE:-pipeline}"

echo "=== Build pipeline image ==="
docker compose --profile "$PROFILE" build pipeline

echo "=== Start infrastructure ==="
docker compose up -d minio postgres qdrant

echo "=== Migrate ==="
docker compose --profile "$PROFILE" run --rm pipeline migrate

echo "=== Corpus status ==="
docker compose --profile "$PROFILE" run --rm pipeline corpus-status

echo "=== Ingest PDFs ==="
docker compose --profile "$PROFILE" run --rm pipeline ingest-dir --dir /app/pdfs

echo "=== Transform ==="
docker compose --profile "$PROFILE" run --rm pipeline transform

echo "Done."
