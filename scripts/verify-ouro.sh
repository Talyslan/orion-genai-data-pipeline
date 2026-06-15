#!/usr/bin/env bash
set -euo pipefail

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-orion-genai-data-pipeline-postgres-1}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-document_embeddings}"

echo "=== PostgreSQL — últimos documentos ==="
docker exec -i "$POSTGRES_CONTAINER" psql -U orion -d orion -c \
  "SELECT file_name, minio_object_key FROM documents ORDER BY created_at DESC LIMIT 10;"

echo ""
echo "=== Qdrant — coleção $QDRANT_COLLECTION ==="
if command -v jq >/dev/null 2>&1; then
  curl -s "$QDRANT_URL/collections/$QDRANT_COLLECTION" | jq .
else
  curl -s "$QDRANT_URL/collections/$QDRANT_COLLECTION"
  echo
fi

echo ""
echo "MinIO console: http://localhost:9001 (bucket bronze → prefixo source/)"
