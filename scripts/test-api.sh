#!/usr/bin/env bash
set -euo pipefail

# Smoke test da Pipeline API (quarta entrega).
# Pré-requisito: docker compose up -d (infra + pipeline-api)

export MSYS_NO_PATHCONV=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

API_HOST="${PIPELINE_API_HOST:-http://localhost:8000}"
API_BASE="${PIPELINE_API_URL:-${API_HOST}/api}"
DOCS_URL="${API_HOST}/api/docs"
WAIT_SECONDS="${API_WAIT_SECONDS:-60}"

wait_for_api() {
  echo "Aguardando ${API_BASE}/health (até ${WAIT_SECONDS}s)..."
  for _ in $(seq 1 "$WAIT_SECONDS"); do
    if curl -sf "${API_BASE}/health" >/dev/null 2>&1; then
      echo "API disponível."
      return 0
    fi
    sleep 1
  done
  echo "FAIL: API não respondeu em ${WAIT_SECONDS}s" >&2
  exit 1
}

assert_json_field() {
  local url="$1"
  local pattern="$2"
  local label="$3"
  local body
  body="$(curl -sf "$url")"
  if ! echo "$body" | grep -q "$pattern"; then
    echo "FAIL: $label — resposta inesperada de $url" >&2
    echo "$body" >&2
    exit 1
  fi
  echo "OK: $label"
}

wait_for_api

echo ""
echo "=== Swagger ==="
curl -sf "$DOCS_URL" | grep -qi swagger && echo "OK: /api/docs"

echo ""
echo "=== Health ==="
assert_json_field "${API_BASE}/health" '"status"' "GET /api/health"

echo ""
echo "=== PDF help ==="
assert_json_field "${API_BASE}/pdf/help" '"documents"' "GET /api/pdf/help"

echo ""
echo "=== Site help ==="
assert_json_field "${API_BASE}/site/help" '"allowed_domains"' "GET /api/site/help"

echo ""
echo "=== Rejeição PDF (document_id inválido) ==="
REJECT_RAW="$(
  curl -s -w $'\nHTTP_CODE:%{http_code}' \
    -X POST "${API_BASE}/pdf" \
    -H "Content-Type: application/json" \
    -d '{"document_id":"__invalid__"}'
)"
REJECT_STATUS="${REJECT_RAW##*HTTP_CODE:}"
REJECT_BODY="${REJECT_RAW%HTTP_CODE:*}"
REJECT_BODY="${REJECT_BODY%$'\n'}"
if [[ "$REJECT_STATUS" != "403" ]]; then
  echo "FAIL: POST /api/pdf inválido deveria retornar 403, obteve $REJECT_STATUS" >&2
  echo "$REJECT_BODY" >&2
  exit 1
fi
echo "$REJECT_BODY" | grep -qE '"enqueued"[[:space:]]*:[[:space:]]*false'
echo "OK: POST /api/pdf rejeitado com enqueued=false"

echo ""
echo "=== Jobs list ==="
assert_json_field "${API_BASE}/jobs?limit=5" '"jobs"' "GET /api/jobs"

echo ""
echo "Pipeline API smoke tests OK"
