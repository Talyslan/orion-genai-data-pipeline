#!/usr/bin/env bash
set -euo pipefail

export MSYS_NO_PATHCONV=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

PASS=0
FAIL=0
WARN=0

ok() {
  echo "  OK  $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "  FAIL $1" >&2
  FAIL=$((FAIL + 1))
}

warn() {
  echo "  WARN $1"
  WARN=$((WARN + 1))
}

check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "$1 disponível"
  else
    fail "$1 não encontrado no PATH"
  fi
}

echo "=== Software ==="
check_cmd docker

if docker compose version >/dev/null 2>&1; then
  ok "docker compose v2 ($(docker compose version --short 2>/dev/null || docker compose version | head -1))"
else
  fail "docker compose v2 não disponível"
fi

DOCKER_MAJOR="$(docker version --format '{{.Server.Version}}' 2>/dev/null | cut -d. -f1 || echo 0)"
if [[ "${DOCKER_MAJOR:-0}" -ge 24 ]]; then
  ok "Docker Engine ${DOCKER_MAJOR}+ (requisito: 24+)"
else
  warn "Docker Engine pode estar abaixo de 24 (detectado: ${DOCKER_MAJOR:-desconhecido})"
fi

echo ""
echo "=== Recursos do host ==="
TOTAL_MEM_KB="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
if [[ "$TOTAL_MEM_KB" -gt 0 ]]; then
  TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
  if [[ "$TOTAL_MEM_GB" -ge 8 ]]; then
    ok "RAM ~${TOTAL_MEM_GB} GB (recomendado: 8 GB+)"
  elif [[ "$TOTAL_MEM_GB" -ge 4 ]]; then
    warn "RAM ~${TOTAL_MEM_GB} GB (mínimo: 4 GB; recomendado: 8 GB+ para embeddings)"
  else
    fail "RAM ~${TOTAL_MEM_GB} GB (mínimo: 4 GB)"
  fi
else
  MEM_DOCKER="$(docker system info --format '{{.MemTotal}}' 2>/dev/null || echo 0)"
  if [[ "$MEM_DOCKER" -gt 0 ]]; then
    MEM_GB=$((MEM_DOCKER / 1024 / 1024 / 1024))
    if [[ "$MEM_GB" -ge 4 ]]; then
      ok "RAM Docker ~${MEM_GB} GB"
    else
      warn "RAM Docker ~${MEM_GB} GB (pode ser insuficiente para BGE-M3)"
    fi
  else
    warn "Não foi possível detectar RAM automaticamente"
  fi
fi

echo ""
echo "=== Serviços de dados (docker compose) ==="
SERVICES=(minio postgres qdrant)
for svc in "${SERVICES[@]}"; do
  if docker compose ps --status running --format '{{.Service}}' 2>/dev/null | grep -qx "$svc"; then
    ok "serviço $svc em execução"
  else
    fail "serviço $svc não está running — execute: docker compose up -d"
  fi
done

if curl -sf http://localhost:9000/minio/health/live >/dev/null 2>&1; then
  ok "MinIO API (localhost:9000)"
else
  fail "MinIO API não responde em localhost:9000"
fi

if curl -sf http://localhost:6333/healthz >/dev/null 2>&1; then
  ok "Qdrant (localhost:6333)"
else
  fail "Qdrant não responde em localhost:6333"
fi

POSTGRES_CONTAINER="$(docker compose ps -q postgres 2>/dev/null | head -1)"
if [[ -n "$POSTGRES_CONTAINER" ]] && docker exec "$POSTGRES_CONTAINER" pg_isready -U orion >/dev/null 2>&1; then
  ok "PostgreSQL (localhost:5433)"
else
  fail "PostgreSQL não está pronto"
fi

echo ""
echo "=== Corpus PDF ==="
PDF_COUNT="$(find pdfs -maxdepth 1 -name '*.pdf' 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$PDF_COUNT" -ge 1 ]]; then
  ok "${PDF_COUNT} PDF(s) em ./pdfs/"
else
  fail "Nenhum PDF em ./pdfs/ — baixe o corpus antes da ingestão"
fi

if [[ -f pdfs/manifest.yaml ]]; then
  ok "pdfs/manifest.yaml presente"
else
  warn "pdfs/manifest.yaml ausente (opcional para ingestão manual)"
fi

echo ""
echo "=== Fase 1 (host) ==="
if command -v uv >/dev/null 2>&1; then
  ok "UV disponível"
  if uv run pytest tests/ -q --tb=no >/dev/null 2>&1; then
    ok "testes da Fase 1 passando (pytest)"
  else
    fail "testes falharam — execute: uv run pytest tests/"
  fi
else
  warn "UV não encontrado — pule verificação de testes no host"
fi

echo ""
echo "=== Rede interna Docker (opcional) ==="
if docker compose --profile pipeline config --services 2>/dev/null | grep -qx pipeline; then
  ok "serviço pipeline definido no compose (profile: pipeline)"
  if docker image inspect orion-genai-pipeline:latest >/dev/null 2>&1; then
    ok "imagem orion-genai-pipeline:latest construída"
    if docker compose --profile pipeline run --rm --no-deps pipeline shell -c \
      "curl -sf http://minio:9000/minio/health/live && curl -sf http://qdrant:6333/healthz && python -c \"import socket; socket.create_connection(('postgres',5432),5).close()\"" \
      >/dev/null 2>&1; then
      ok "pipeline resolve minio, postgres e qdrant na rede interna"
    else
      warn "conectividade interna falhou — reconstrua: docker compose --profile pipeline build pipeline"
    fi
  else
    warn "imagem pipeline ainda não construída — execute: docker compose --profile pipeline build pipeline"
  fi
else
  fail "serviço pipeline ausente em docker-compose.yml"
fi

echo ""
echo "=== Resumo ==="
echo "  Passou: $PASS | Falhou: $FAIL | Avisos: $WARN"

if [[ "$FAIL" -gt 0 ]]; then
  echo ""
  echo "Corrija os itens FAIL antes de continuar a Fase 2."
  exit 1
fi

echo ""
echo "Pré-requisitos OK. Próximo passo: docker compose --profile pipeline build pipeline"
exit 0
