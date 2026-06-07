# toll-analytics-platform

Monorepo de uma **plataforma de dados de auditoria de vale-pedágio** — da
transformação à orquestração. Dados **sintéticos** (nenhum dado real de cliente).

```
toll-analytics-platform/
├── ingestion-toll-analytics/  # INGESTÃO/EL (dlt → schema landing no DuckDB)
├── dbt-toll-analytics/        # TRANSFORMAÇÃO (dbt + DuckDB dev / Databricks prod)
├── dbt-toll-exec/             # dbt MESH: downstream que consome os models public
├── quality-toll-analytics/    # DATA QUALITY independente (Soda Core)
├── bi-toll-analytics/         # BI / serving (Evidence.dev → site estático)
├── airflow-toll-analytics/    # ORQUESTRAÇÃO (Airflow + Astronomer Cosmos)
├── infra/terraform/           # IaC do warehouse de prod (Databricks/Unity Catalog)
├── .pre-commit-config.yaml    # qualidade antes do commit (ruff, yaml, etc.)
└── .github/workflows/         # CI/CD dos projetos (rodam por working-directory)
```

## Os projetos
| Projeto | O que faz | Entrar |
|---|---|---|
| **[ingestion-toll-analytics](ingestion-toll-analytics/)** | EL com **dlt**: lê arquivos de landing (CSV) e carrega no schema `landing` do DuckDB (merge/replace, metadados, `''→NULL`). O "E" e o "L" antes do "T". | [README](ingestion-toll-analytics/README.md) |
| **[dbt-toll-analytics](dbt-toll-analytics/)** | Medallion (landing→silver→gold), tarifa point-in-time, contracts, unit tests, Semantic Layer, sources+freshness, observabilidade (Elementary). Dev em DuckDB, **prod em Databricks**. | [README](dbt-toll-analytics/README.md) · [PLANO](dbt-toll-analytics/PLANO_DO_PROJETO.md) |
| **[dbt-toll-exec](dbt-toll-exec/)** | **dbt Mesh**: projeto downstream que consome só os models `public` do upstream via cross-project `ref()` (dbt-loom). Prova a fronteira de acesso (ADR-18). | [README](dbt-toll-exec/README.md) |
| **[quality-toll-analytics](quality-toll-analytics/)** | **Data Quality independente** (Soda Core): checks nos marts, gate no Airflow e no CI. | [README](quality-toll-analytics/README.md) |
| **[bi-toll-analytics](bi-toll-analytics/)** | **BI / serving** (Evidence.dev): painel executivo lendo os marts → site estático publicado no Pages (com o lineage do dbt em `/lineage/`). | [README](bi-toll-analytics/README.md) |
| **[airflow-toll-analytics](airflow-toll-analytics/)** | Orquestra **ingestão → transform → DQ gate (Soda)** com Cosmos: cada model/test = 1 task, schedule, retries, freshness gate, alertas, DAG de observabilidade. | [README](airflow-toll-analytics/README.md) |

## Validar tudo (local)
```bash
# 1) Ingestão (EL) — dlt carrega os arquivos de landing no schema `landing`
cd ingestion-toll-analytics
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python toll_ingestion.py

# 2) Transformação (dbt) — consome via source('toll_raw', ...)
cd ../dbt-toll-analytics
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
dbt deps --profiles-dir . && dbt build --profiles-dir .   # PASS, WARN intencional
#   (atalho: `make build` roda a ingestão + build + checa a doc)

# 3) Orquestração (Airflow + Cosmos) — sobe Airflow e roda ingestão→transform
cd ../airflow-toll-analytics
bash scripts/validate_local.sh                            # state=success, ponta-a-ponta
```

## CI (GitHub Actions)
- `dbt_ci.yml` — ingestão (dlt) + `dbt build` + SQLFluff + check de drift da documentação
- `pages_site.yml` — **site no GitHub Pages**: dashboard BI (Evidence) em `/` + lineage do dbt em `/lineage/` (habilitar 1x: Settings → Pages → Source: GitHub Actions)
- `dbt_slim_ci.yml` — Slim CI (`state:modified+ --defer`) em PRs
- `governance_ci.yml` — **mesh + DQ**: upstream → Soda Core → downstream (dbt-loom)
- `observability.yml` — testes de anomalia (Elementary), agendado
- `airflow_ci.yml` — teste de integridade dos DAGs (sem erro de import)
- `pre_commit.yml` — roda os hooks de pre-commit (ruff, yaml…) no CI
- `terraform_ci.yml` — valida a IaC do Databricks (`terraform validate`, sem apply)
- `cd_deploy.yml` — **CD** manual com promoção staging→prod (GitHub Environments)

**Qualidade local:** `pip install pre-commit && pre-commit install` — roda ruff
(lint+format), yamllint e checagens básicas a cada commit.

## Escala / benchmark
`bash scripts/benchmark.sh 100000` gera 100k transações (faker), ingere (dlt) e roda
`dbt build`, medindo. Medido: **~23 s** total no DuckDB (fato com 100.472 linhas,
`PASS=192 ERROR=0`); a auditoria encontra ~6.988 suspeitas. Para volumes maiores, o
`prod` (Databricks) usaria incremental **microbatch** + **clustering** (ADR-24). O dataset
de escala é gerado/gitignored — o dataset curado pequeno fica para os testes determinísticos.

> **Stack-alvo:** o `dev` roda offline em DuckDB (reprodutível por qualquer um); o
> `prod` é Databricks real (Unity Catalog + Delta) — os models SQL não mudam, só a
> conexão (`profiles.yml`).
