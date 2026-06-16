#!/usr/bin/env bash
set -euo pipefail

# Git Bash (Windows) converte /app/... em path do host — desabilitar
export MSYS_NO_PATHCONV=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

PROFILE="${COMPOSE_PROFILE:-pipeline}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SKIP_TRANSFORM="${SKIP_TRANSFORM:-0}"
SKIP_INGEST="${SKIP_INGEST:-0}"
TRANSFORM_ALL="${TRANSFORM_ALL:-0}"
TRANSFORM_OBJECT_KEY="${TRANSFORM_OBJECT_KEY:-source/2026/06/16/microservices-on-aws.pdf}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-orion-genai-data-pipeline-postgres-1}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-document_embeddings}"

compose_run() {
  docker compose --profile "$PROFILE" run --rm "$@"
}

echo "=== Pré-requisitos ==="
bash scripts/verify-docker-prereqs.sh

if [[ "$SKIP_BUILD" != "1" ]]; then
  echo ""
  echo "=== Build pipeline (CPU-only PyTorch) ==="
  docker compose --profile "$PROFILE" build pipeline
fi

echo ""
echo "=== Infraestrutura ==="
docker compose up -d minio postgres qdrant

echo "Aguardando serviços..."
for _ in $(seq 1 30); do
  if docker compose ps --status running --format '{{.Service}} {{.Health}}' 2>/dev/null \
    | grep -q "postgres healthy" \
    && docker compose ps --status running --format '{{.Service}} {{.Health}}' 2>/dev/null \
    | grep -q "qdrant healthy"; then
    break
  fi
  sleep 2
done

echo ""
echo "=== Tesseract no container ==="
compose_run --no-deps pipeline shell -c "tesseract --version | head -1"

echo ""
echo "=== Migrate ==="
compose_run pipeline migrate

echo ""
echo "=== Corpus no volume ==="
PDF_COUNT="$(compose_run --no-deps pipeline shell -c "ls -1 /app/pdfs/*.pdf 2>/dev/null | wc -l")"
echo "PDFs montados: $PDF_COUNT"
if [[ "${PDF_COUNT// /}" -lt 1 ]]; then
  echo "FAIL: nenhum PDF em /app/pdfs" >&2
  exit 1
fi

echo ""
echo "=== Ingestão PDF ==="
if [[ "$SKIP_INGEST" != "1" ]]; then
  compose_run pipeline ingest-dir
else
  echo "SKIP_INGEST=1 — pulando ingestão"
fi

if [[ "$SKIP_TRANSFORM" != "1" ]]; then
  echo ""
  if [[ "$TRANSFORM_ALL" == "1" ]]; then
    echo "=== Transformação (lote completo — pode demorar horas em PDFs grandes) ==="
    compose_run pipeline transform
  else
    echo "=== Transformação (1 PDF de teste: $TRANSFORM_OBJECT_KEY) ==="
    echo "    Use TRANSFORM_ALL=1 para processar todo o Bronze."
    compose_run pipeline transform --object-key "$TRANSFORM_OBJECT_KEY"
  fi

  echo ""
  echo "=== Verificação PostgreSQL + Qdrant ==="
  DOC_COUNT="$(docker exec "$POSTGRES_CONTAINER" psql -U orion -d orion -t -A -c \
    "SELECT COUNT(*) FROM documents WHERE file_name LIKE '%.pdf';")"
  echo "Documentos PDF no PostgreSQL: $DOC_COUNT"
  if [[ "$DOC_COUNT" -lt 1 ]]; then
    echo "FAIL: nenhum documento PDF em PostgreSQL" >&2
    exit 1
  fi

  if command -v jq >/dev/null 2>&1; then
    QDRANT_POINTS="$(curl -sf "$QDRANT_URL/collections/$QDRANT_COLLECTION" | jq -r '.result.points_count')"
  else
    QDRANT_POINTS="$(curl -sf "$QDRANT_URL/collections/$QDRANT_COLLECTION" | grep -o '"points_count":[0-9]*' | cut -d: -f2)"
  fi
  echo "Pontos no Qdrant ($QDRANT_COLLECTION): $QDRANT_POINTS"
  if [[ "${QDRANT_POINTS:-0}" -lt 1 ]]; then
    echo "FAIL: coleção Qdrant vazia" >&2
    exit 1
  fi

  echo ""
  echo "=== Rastreabilidade (trace) ==="
  CHUNK_ID="$(docker exec "$POSTGRES_CONTAINER" psql -U orion -d orion -t -A -c \
    "SELECT c.id FROM chunks c ORDER BY c.created_at DESC LIMIT 1;")"
  if [[ -z "$CHUNK_ID" ]]; then
    echo "FAIL: nenhum chunk para trace" >&2
    exit 1
  fi
  echo "Chunk: $CHUNK_ID"
  compose_run pipeline trace "$CHUNK_ID"

  echo ""
  echo "=== Idempotência (re-execução do mesmo objeto) ==="
  if [[ "$TRANSFORM_ALL" == "1" ]]; then
    TRANSFORM_OUT="$(compose_run pipeline transform 2>&1 | tail -20)"
  else
    TRANSFORM_OUT="$(compose_run pipeline transform --object-key "$TRANSFORM_OBJECT_KEY" 2>&1)"
  fi
  echo "$TRANSFORM_OUT"
  if echo "$TRANSFORM_OUT" | grep -qi "skipped"; then
    echo "OK: idempotência confirmada (skipped)"
  else
    echo "WARN: objeto não apareceu como skipped"
  fi
fi

echo ""
echo "Docker pipeline OK"
