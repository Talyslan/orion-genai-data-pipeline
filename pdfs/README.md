# Corpus PDF — AWS Whitepapers

**Tema:** Performance Frontend, Web Applications e Boas Práticas de Engenharia.

**Fonte:** PDFs oficiais AWS (Well-Architected Framework, pilares e whitepapers).

## Corpus mínimo (6 arquivos)

| Arquivo | Documento | Foco | Status local |
|---------|-----------|------|--------------|
| `wellarchitected-framework.pdf` | AWS Well-Architected Framework | Visão geral dos pilares | Disponível |
| `wellarchitected-performance-efficiency-pillar.pdf` | Performance Efficiency Pillar | Otimização e uso eficiente de recursos | Disponível |
| `wellarchitected-reliability-pillar.pdf` | Reliability Pillar | Resiliência e disponibilidade | Disponível |
| `wellarchitected-security-pillar.pdf` | Security Pillar | Segurança em workloads cloud | Disponível |
| `wellarchitected-sustainability-pillar.pdf` | Sustainability Pillar | Sustentabilidade e eficiência | Disponível |
| `microservices-on-aws.pdf` | Microservices on AWS | Arquitetura de microserviços | Disponível |

## Complementares (opcionais)

| Documento | Arquivo sugerido | Status |
|-----------|------------------|--------|
| Serverless Architectures with AWS Lambda | `serverless-architectures-lambda.pdf` | URL no manifesto — a baixar |
| Architecting for the Cloud | `architecting-for-the-cloud.pdf` | Download manual na página AWS |

## Como obter os PDFs

### Manual (recomendado hoje)

1. Abra a página de documentação na coluna **Página** abaixo.
2. Use o link **Download PDF** oficial da AWS.
3. Salve o arquivo nesta pasta com o nome indicado em **Arquivo**.

### Automático

```bash
uv run python -m pipeline.ingestion.cli download-corpus
# ou
bash scripts/download-pdfs.sh
```

Baixa entradas com URL em `manifest.yaml`, valida `%PDF` e ignora arquivos cujo hash SHA-256 já coincide com o remoto.

## Origem e URLs

| Arquivo | Página AWS | PDF direto |
|---------|------------|------------|
| `wellarchitected-framework.pdf` | [Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html) | [PDF](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/framework/wellarchitected-framework.pdf) |
| `wellarchitected-performance-efficiency-pillar.pdf` | [Performance](https://docs.aws.amazon.com/wellarchitected/latest/performance-efficiency-pillar/welcome.html) | [PDF](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/performance-efficiency-pillar/wellarchitected-performance-efficiency-pillar.pdf) |
| `wellarchitected-reliability-pillar.pdf` | [Reliability](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html) | [PDF](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/reliability-pillar/wellarchitected-reliability-pillar.pdf) |
| `wellarchitected-security-pillar.pdf` | [Security](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html) | [PDF](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/security-pillar/wellarchitected-security-pillar.pdf) |
| `wellarchitected-sustainability-pillar.pdf` | [Sustainability](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/welcome.html) | [PDF](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/sustainability-pillar/wellarchitected-sustainability-pillar.pdf) |
| `microservices-on-aws.pdf` | [Microservices](https://docs.aws.amazon.com/whitepapers/latest/microservices-on-aws/microservices-on-aws.html) | [PDF](https://docs.aws.amazon.com/pdfs/whitepapers/latest/microservices-on-aws/microservices-on-aws.pdf) |

**Manifesto versionado:** `manifest.yaml` (URLs validadas em 2026-06-15).

## Verificar corpus antes da ingestão

```bash
uv run python -m pipeline.ingestion.cli corpus-status
uv run python -m pipeline.ingestion.cli ingest-dir --dir ./pdfs
```

## Consultas semânticas esperadas (pós-transformação)

Após ingestão e transformação, a base deve responder a perguntas como:

- *Quais são os pilares do AWS Well-Architected Framework?*
- *Como otimizar performance efficiency em aplicações web na AWS?*
- *Quais tradeoffs existem em arquiteturas de microserviços?*
- *Quais práticas de reliability se aplicam a aplicações frontend distribuídas?*
