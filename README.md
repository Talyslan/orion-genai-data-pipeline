# Orion Data Pipeline to Generative AI

Pipeline de Engenharia de Dados para IA Generativa. Coleta conteúdo via web scraping, armazena dados brutos em um data lake (MinIO), transforma e segmenta o texto, gera embeddings e persiste chunks textuais e vetores com rastreabilidade completa.

## Objetivo

Construir um pipeline reproduzível que:

- Ingere arquivos locais em lote ou via web scraping
- Persiste arquivos brutos no MinIO (camada Bronze)
- Limpa, segmenta e vetoriza o conteúdo (camada de transformação)
- Armazena chunks em PostgreSQL e vetores em Qdrant (camada Ouro)
- Mantém rastreabilidade entre fonte original, arquivo, chunk e vetor

A fase atual inclui ingestão de PDF e arquivos locais em lote (terceira entrega — Fase 1), transformação para PostgreSQL/Qdrant (segunda entrega — Fase 2) e scraping por URL (primeira entrega).

## Arquitetura

```text
┌────────────────────┐
│ Fonte de Dados     │
│ (Arquivos locais   │
│  ou Website)       │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Ingestion Layer    │
│ Local / Scraper    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Persistência Local │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Bronze Layer       │
│ MinIO              │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Transformation     │
│ Pipeline           │
└──────┬───────┬─────┘
       │       │
       ▼       ▼
 PostgreSQL  Qdrant
```

## Stack utilizada

| Categoria          | Tecnologia             |
| ------------------ | ---------------------- |
| Linguagem          | Python 3.12+           |
| Dependências       | UV                     |
| Controle de versão | Git                    |
| Containers         | Docker, Docker Compose |
| Data lake          | MinIO                  |
| Banco relacional   | PostgreSQL             |
| Banco vetorial     | Qdrant                 |
| Embeddings         | BGE-M3                 |
| Configuração       | Pydantic Settings      |
| Logging            | Structlog              |
| Qualidade          | Ruff, Pytest           |
| Hooks              | pre-commit             |

## Instruções de execução

### Pré-requisitos

- Python 3.12+
- [UV](https://docs.astral.sh/uv/)
- Docker e Docker Compose

### Ambiente virtual

```bash
python -m venv .venv
```

**Windows**

```bash
.venv\Scripts\activate
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

### Dependências

Com o ambiente virtual ativo:

```bash
uv sync
```

### Variáveis de ambiente

Copie o arquivo de exemplo e ajuste conforme necessário:

```bash
cp .env.example .env
```

Principais variáveis para ingestão local:

| Variável                 | Descrição                   | Padrão              |
| ------------------------ | --------------------------- | ------------------- |
| `DATA_SOURCE_DIR`        | Diretório raiz dos arquivos | `./pdfs`            |
| `DATA_SOURCE_EXTENSIONS` | Extensões aceitas (vírgula) | `.txt,.md,.pdf`     |
| `LOCAL_OUTPUT_DIR`       | Saída local antes do MinIO  | `data/local`        |
| `PDF_EXTRACTION_MODE`    | Modo de extração na transformação | `structured`  |
| `PDF_OCR_ENABLED`        | OCR para páginas escaneadas | `true`              |

Corpus PDF (AWS Whitepapers): coloque os arquivos em `./pdfs/`. Os binários `.pdf` estão no `.gitignore`; o manifesto e o README em `pdfs/` são versionados. Veja [pdfs/README.md](pdfs/README.md) para URLs e instruções de download.

OCR (Tesseract): para PDFs escaneados, instale o Tesseract no SO ou use `uv sync --group ocr` e configure `TESSERACT_CMD` / `TESSDATA_PREFIX` no `.env` (ver task 02 em `specs/terceira-entrega/`).

### Setup inicial (corpus PDF)

```bash
cp .env.example .env
# Ajustar se necessário:
# DATA_SOURCE_DIR=./pdfs
# DATA_SOURCE_EXTENSIONS=.txt,.md,.pdf
# PDF_EXTRACTION_MODE=structured
# PDF_OCR_ENABLED=true

uv sync
# OCR opcional: uv sync --group ocr
docker compose up -d
uv run python -m pipeline.transform.cli migrate
```

Pipeline completo em um comando:

```bash
bash scripts/run-corpus-pdf.sh
```

```bash
# Verificar se o corpus mínimo está completo
uv run python -m pipeline.ingestion.cli corpus-status
```

### Ingestão de arquivos locais

```bash
# Texto / Markdown (segunda entrega)
git clone https://github.com/sandeco/prompts
bash scripts/coleta.sh ./prompts/caminho/para/arquivo.txt
uv run python -m pipeline.ingestion.cli ingest-dir --dir ./prompts

# PDF (terceira entrega — upload binário para Bronze)
bash scripts/coleta.sh ./pdfs/wellarchitected-framework.pdf
uv run python -m pipeline.ingestion.cli ingest-file ./pdfs/wellarchitected-framework.pdf
uv run python -m pipeline.ingestion.cli ingest-dir --dir ./pdfs

# Alternativa shell (arquivo a arquivo)
for file in ./pdfs/*.pdf; do
  bash scripts/coleta.sh "$file"
done
```

### Processamento em lote — corpus PDF (6 whitepapers)

Ordem recomendada para processar todo o corpus AWS em `./pdfs/`:

```bash
docker compose up -d
uv run python -m pipeline.transform.cli migrate   # primeira execução
uv run python -m pipeline.ingestion.cli corpus-status
uv run python -m pipeline.ingestion.cli ingest-dir --dir ./pdfs
uv run orion-transform run
```

A transformação processa todos os objetos sob `source/` no Bronze, incluindo `.pdf` ingeridos.

| Arquivo | Páginas (aprox.) | Tema |
| ------- | ---------------- | ---- |
| `wellarchitected-framework.pdf` | ~80+ | Framework Well-Architected |
| `wellarchitected-performance-efficiency-pillar.pdf` | ~50+ | Performance |
| `wellarchitected-reliability-pillar.pdf` | ~50+ | Reliability |
| `wellarchitected-security-pillar.pdf` | ~50+ | Security |
| `wellarchitected-sustainability-pillar.pdf` | ~30+ | Sustainability |
| `microservices-on-aws.pdf` | ~40+ | Microserviços |

Embeddings com BGE-M3 em CPU podem levar **vários minutos** por documento extenso. A saída do transform mostra progresso:

```text
[1/6] Processing source/2026/06/15/wellarchitected-framework.pdf...
  -> done (chunks=142, embeddings=142)
```

Falhas parciais não abortam o lote: ingestão e transformação retornam código `1` se `failed > 0` e listam os arquivos/object keys com erro.

### Verificação (Bronze e Ouro)

**MinIO (Bronze)**

1. Abrir http://localhost:9001
2. Bucket `bronze` → prefixo `source/`
3. Confirmar objetos `.pdf` com data do upload

**PostgreSQL e Qdrant (Ouro)**

```bash
bash scripts/verify-ouro.sh
```

Ou manualmente:

```bash
docker exec -it orion-genai-data-pipeline-postgres-1 psql -U orion -d orion -c \
  "SELECT file_name, minio_object_key FROM documents ORDER BY created_at DESC LIMIT 10;"

curl -s http://localhost:6333/collections/document_embeddings | jq .
```

**Rastreabilidade** — a partir de um `chunk_id` retornado pela transformação ou consulta ao PostgreSQL:

```bash
uv run python -m pipeline.transform.cli trace <chunk-uuid>
```

A saída inclui `source_format`, `source_path` (PDF em `./pdfs/`) e `minio_object_key`.

### Troubleshooting

| Problema | Verificação |
| -------- | ----------- |
| PDF não ingerido | Extensão em `DATA_SOURCE_EXTENSIONS`? Arquivo existe em `DATA_SOURCE_DIR`? |
| Texto vazio após extração | Ativar OCR (`PDF_OCR_ENABLED=true`); verificar Tesseract instalado |
| Tabelas desordenadas | Usar `PDF_EXTRACTION_MODE=structured` |
| OCR lento | Reduzir `PDF_OCR_DPI`; limitar `PDF_MAX_PAGES` em dev |
| `TesseractNotFoundError` | Instalar Tesseract no SO ou configurar `TESSERACT_CMD` no `.env` |

### Ingestão por URL (legado — primeira entrega)

```bash
uv run python src/main.py
```

Configure `SCRAPE_URL` no `.env` antes de executar.

### Serviços (MinIO, PostgreSQL, Qdrant)

```bash
docker compose up -d
```

| Serviço       | URL                   | Credenciais                     |
| ------------- | --------------------- | ------------------------------- |
| MinIO API     | http://localhost:9000 | `minioadmin` / `minioadmin`     |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin`     |
| PostgreSQL    | `localhost:5433`      | `orion` / `orion` (db: `orion`) |
| Qdrant        | http://localhost:6333 | —                               |

### Transformação (Fase 2)

Após ingerir arquivos no Bronze, execute a transformação:

```bash
# Migração do banco (primeira vez) — opção A: via Python (recomendado no Windows)
uv run python -m pipeline.transform.cli migrate
# ou: bash scripts/migrate.sh

# Opção B: via Docker (sem instalar psql no Windows)
docker exec -i orion-genai-data-pipeline-postgres-1 psql -U orion -d orion < scripts/migrations/001_initial.sql

# Processar todos os objetos Bronze
uv run python -m pipeline.transform.cli run

# Processar um objeto específico
uv run python -m pipeline.transform.cli run --object-key source/2026/06/08/foo.md

# Rastreabilidade por chunk_id (inclui source_format e caminho do PDF)
uv run python -m pipeline.transform.cli trace <chunk-uuid>
```

Atalho:

```bash
uv run orion-transform run
```

Variáveis principais:

| Variável          | Descrição                 | Padrão                                          |
| ----------------- | ------------------------- | ----------------------------------------------- |
| `CHUNK_SIZE`      | Tamanho máximo do chunk   | `1200`                                          |
| `CHUNK_OVERLAP`   | Sobreposição entre chunks | `200`                                           |
| `EMBEDDING_MODEL` | Modelo de embeddings      | `BAAI/bge-m3`                                   |
| `POSTGRES_URL`    | Conexão PostgreSQL        | `postgresql://orion:orion@localhost:5433/orion` |
| `QDRANT_URL`      | URL do Qdrant             | `http://localhost:6333`                         |

### Testes

```bash
pytest
```

Testes de ingestão e transformação (PDF):

```bash
pytest tests/ingestion/ tests/transform/ -v
```

### Qualidade de código

Instalar os hooks (uma vez, com o venv ativo):

```bash
pre-commit install
```

Executar manualmente em todos os arquivos:

```bash
pre-commit run --all-files
```

Ferramentas individuais:

```bash
ruff format .
ruff check .
```

Validar mensagem de commit manualmente:

```bash
cz check --message "feat: add scraper module"
```

Criar commit interativo no padrão Conventional Commits:

```bash
cz commit
```

## Estrutura do projeto

```text
orion-genai-data-pipeline/
├── src/pipeline/
│   ├── ingestion/
│   ├── bronze/
│   ├── transform/
│   ├── storage/
│   └── shared/
│       ├── config/
│       ├── logger/
│       ├── schemas/
│       └── utils/
├── tests/
├── docs/
├── docker/
├── scripts/
│   ├── coleta.sh
│   ├── migrate.sh
│   ├── run-corpus-pdf.sh
│   └── verify-ouro.sh
├── .env.example
├── pyproject.toml
└── docker-compose.yml
```

## Documentação

Especificações detalhadas em `specs/`:

- [Setup e ambiente](specs/basis/README.md)
- [Primeira entrega](specs/primeira-entrega/readme.md)
- [Segunda entrega](specs/segunda-entrega/readme.md)
- [Especificação técnica](specs/spec-tech.md)
