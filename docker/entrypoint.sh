#!/usr/bin/env bash
set -euo pipefail

CMD="${1:-help}"
shift || true

case "$CMD" in
  migrate)
    exec python -m pipeline.transform.cli migrate "$@"
    ;;
  download-corpus)
    exec python -m pipeline.ingestion.cli download-corpus "$@"
    ;;
  corpus-status)
    exec python -m pipeline.ingestion.cli corpus-status "$@"
    ;;
  ingest-file)
    exec python -m pipeline.ingestion.cli ingest-file "$@"
    ;;
  ingest-dir)
    exec python -m pipeline.ingestion.cli ingest-dir "$@"
    ;;
  transform)
    exec python -m pipeline.transform.cli run "$@"
    ;;
  trace)
    exec python -m pipeline.transform.cli trace "$@"
    ;;
  shell)
    exec /bin/bash "$@"
    ;;
  help|--help)
    cat <<EOF
Orion Pipeline — comandos disponíveis:

  migrate              Aplicar migration PostgreSQL
  download-corpus      Baixar PDFs do manifest AWS (opcional)
  corpus-status        Verificar corpus local
  ingest-file <path>   Ingerir um arquivo
  ingest-dir [--dir]   Ingerir diretório (default: DATA_SOURCE_DIR)
  transform            Transformar objetos Bronze → Ouro
  trace <chunk-id>     Rastreabilidade
  shell                Bash interativo

Exemplos:
  docker compose --profile pipeline run --rm pipeline migrate
  docker compose --profile pipeline run --rm pipeline ingest-dir --dir /app/pdfs
  docker compose --profile pipeline run --rm pipeline transform
EOF
    ;;
  *)
    echo "Comando desconhecido: $CMD" >&2
    exit 1
    ;;
esac
