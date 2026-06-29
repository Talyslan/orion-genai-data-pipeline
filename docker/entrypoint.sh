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
  serve)
    python -m pipeline.transform.cli migrate
    exec uvicorn api.app:app --host 0.0.0.0 --port 8000 "$@"
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
  serve                Subir API HTTP (migrate + uvicorn :8000)
  trace <chunk-id>     Rastreabilidade
  shell                Bash interativo

Exemplos:
  docker compose --profile pipeline run --rm pipeline migrate
  docker compose --profile pipeline run --rm pipeline ingest-dir
  docker compose --profile pipeline run --rm pipeline transform
  docker compose --profile pipeline run --rm pipeline transform --object-key source/2026/06/16/foo.pdf
  docker compose up -d pipeline-api
EOF
    ;;
  *)
    echo "Comando desconhecido: $CMD" >&2
    exit 1
    ;;
esac
