# Orion Data Pipeline to Generative AI

Pipeline de Engenharia de Dados para IA Generativa. Coleta conteúdo via web scraping, armazena dados brutos em um data lake (MinIO), transforma e segmenta o texto, gera embeddings e persiste chunks textuais e vetores com rastreabilidade completa.

## Objetivo

Construir um pipeline reproduzível que:

- Extrai dados de sites via web scraping
- Persiste arquivos brutos no MinIO (camada Bronze)
- Limpa, segmenta e vetoriza o conteúdo (camada de transformação)
- Armazena chunks em PostgreSQL e vetores em Qdrant (camada Ouro)
- Mantém rastreabilidade entre fonte original, arquivo, chunk e vetor

A fase atual foca no setup do ambiente e na primeira entrega: scraping → arquivo local → upload MinIO.

## Arquitetura

```text
┌────────────────────┐
│ Fonte de Dados     │
│ (Website)          │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Ingestion Layer    │
│ Web Scraper        │
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

### Serviços (MinIO)

```bash
docker compose up -d
```

Console MinIO: http://localhost:9001
Credenciais padrão: `minioadmin` / `minioadmin`

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
├── .env.example
├── pyproject.toml
└── docker-compose.yml
```

## Documentação

Especificações detalhadas em `specs/`:

- [Setup e ambiente](specs/basis/README.md)
- [Primeira entrega](specs/primeira-entrega/readme.md)
- [Especificação técnica](specs/spec-tech.md)
