# App Geração dos Dados

Container one-shot que dispara o pipeline via HTTP (`pipeline-api`).

## Uso local

```bash
export PIPELINE_API_URL=http://localhost:8000/api
uv run orion-geracao run --mode corpus
uv run orion-geracao run --mode site
uv run orion-geracao run --mode all
uv run orion-geracao run --mode single --document-id wellarchitected-framework
uv run orion-geracao health
```

## Docker

```bash
docker compose up -d pipeline-api
docker compose run --rm geracao run --mode corpus
```

## Variáveis

| Variável | Default | Descrição |
|----------|---------|-----------|
| `PIPELINE_API_URL` | `http://localhost:8000/api` | Base da API (com `/api`) |
| `GERACAO_POLL_INTERVAL_SECONDS` | `5` | Intervalo entre polls |
| `GERACAO_JOB_TIMEOUT_SECONDS` | `3600` | Timeout por lote de jobs |
| `GERACAO_SITE_URLS` | — | URLs comma-separated (override do `/api/site/help`) |

Guia completo: [specs/quarta-entrega/geracao.md](../../specs/quarta-entrega/geracao.md)
