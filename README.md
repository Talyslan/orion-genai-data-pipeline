# Orion Data Pipeline to Generative AI

Pipeline de Engenharia de Dados para IA Generativa. Coleta conteúdo via web scraping, armazena dados brutos em um data lake (MinIO), transforma e segmenta o texto, gera embeddings e persiste chunks textuais e vetores com rastreabilidade completa.

## Objetivo

Construir um pipeline reproduzível que:

- Ingere arquivos locais em lote ou via web scraping
- Persiste arquivos brutos no MinIO (camada Bronze)
- Limpa, segmenta e vetoriza o conteúdo (camada de transformação)
- Armazena chunks em PostgreSQL e vetores em Qdrant (camada Ouro)
- Mantém rastreabilidade entre fonte original, arquivo, chunk e vetor

A fase atual inclui ingestão local em lote (segunda entrega — Fase 1) e scraping por URL (primeira entrega).

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

| Variável                 | Descrição                   | Padrão       |
| ------------------------ | --------------------------- | ------------ |
| `DATA_SOURCE_DIR`        | Diretório raiz dos arquivos | `./prompts`  |
| `DATA_SOURCE_EXTENSIONS` | Extensões aceitas (vírgula) | `.txt,.md`   |
| `LOCAL_OUTPUT_DIR`       | Saída local antes do MinIO  | `data/local` |

### Ingestão de arquivos locais

```bash
# Clonar dados de referência
git clone https://github.com/sandeco/prompts

# Um arquivo
bash scripts/coleta.sh ./prompts/caminho/para/arquivo.txt

# Lote (shell)
find ./prompts -type f -name "*.txt" -exec bash scripts/coleta.sh {} \;

# Lote (Python)
uv run python -m pipeline.ingestion.cli ingest-dir --dir ./prompts
```

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

# Rastreabilidade por chunk_id
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
| `POSTGRES_URL`    | Conexão PostgreSQL        | `postgresql://orion:orion@localhost:5432/orion` |
| `QDRANT_URL`      | URL do Qdrant             | `http://localhost:6333`                         |

### Testes

```bash
pytest
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
├── scripts/
├── docker/
├── scripts/
│   └── coleta.sh
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
