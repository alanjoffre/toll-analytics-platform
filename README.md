# toll-analytics-platform

Monorepo de uma **plataforma de dados de auditoria de vale-pedágio** — da
transformação à orquestração. Dados **sintéticos** (nenhum dado real de cliente).

```
toll-analytics-platform/
├── dbt-toll-analytics/        # TRANSFORMAÇÃO (dbt + DuckDB dev / Databricks prod)
├── airflow-toll-analytics/    # ORQUESTRAÇÃO (Airflow + Astronomer Cosmos)
└── .github/workflows/         # CI dos dois projetos (rodam por working-directory)
```

## Os dois projetos
| Projeto | O que faz | Entrar |
|---|---|---|
| **[dbt-toll-analytics](dbt-toll-analytics/)** | Medallion (bronze→silver→gold), tarifa point-in-time, contracts, unit tests, Semantic Layer, sources+freshness, observabilidade (Elementary). Dev em DuckDB, **prod em Databricks**. | [README](dbt-toll-analytics/README.md) · [PLANO](dbt-toll-analytics/PLANO_DO_PROJETO.md) |
| **[airflow-toll-analytics](airflow-toll-analytics/)** | Orquestra o dbt com Cosmos: cada model/test = 1 task (lineage real), schedule, retries, freshness gate, alertas, DAG de observabilidade. | [README](airflow-toll-analytics/README.md) |

## Validar tudo (local)
```bash
# 1) Transformação (dbt)
cd dbt-toll-analytics
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
dbt deps --profiles-dir . && dbt build --profiles-dir .   # PASS, WARN=1 intencional

# 2) Orquestração (Airflow + Cosmos) — sobe Airflow num venv e roda o pipeline
cd ../airflow-toll-analytics
bash scripts/validate_local.sh                            # state=success, ponta-a-ponta
```

## CI (GitHub Actions)
- `dbt_ci.yml` — `dbt build` + SQLFluff + check de drift da documentação
- `dbt_docs.yml` — publica o `dbt docs` no **GitHub Pages** (habilitar 1x: Settings → Pages → Source: GitHub Actions)
- `observability.yml` — testes de anomalia (Elementary), agendado
- `airflow_ci.yml` — teste de integridade dos DAGs (sem erro de import)

> **Stack-alvo:** o `dev` roda offline em DuckDB (reprodutível por qualquer um); o
> `prod` é Databricks real (Unity Catalog + Delta) — os models SQL não mudam, só a
> conexão (`profiles.yml`).
