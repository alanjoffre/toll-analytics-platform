# dbt-toll-exec — projeto downstream (dbt Mesh)

Projeto dbt **separado** (relatório executivo) que consome SÓ os models **`public`**
do projeto [`../dbt-toll-analytics`](../dbt-toll-analytics) via **cross-project ref**
(`ref('toll_analytics', 'modelo')`). É a demonstração de **dbt Mesh / governança
multi-projeto**: times diferentes, repositórios/projetos diferentes, contrato claro.

```
toll_analytics (upstream)              toll_exec (este projeto, downstream)
  marts PUBLIC ───────[cross-project ref via dbt-loom]──────▶ exec_audit_overview
  (audit, agg, dims...)                                       exec_plaza_scorecard
```

## Como o cross-project ref funciona aqui
- `dependencies.yml` declara o projeto upstream (`projects: - name: toll_analytics`).
- `dbt_loom.config.yml` aponta para o **manifest** do upstream (`../dbt-toll-analytics/target/manifest.json`).
- O plugin **dbt-loom** injeta os nós do upstream em dbt-core (o cross-project ref
  nativo é do dbt Cloud). Crucial: o dbt-loom **só expõe os models `public`** — então
  `ref('toll_analytics', 'stg_*')` (protected) **falha**, provando a fronteira de
  acesso definida no upstream (ADR-18). Governança de verdade.

## Rodar
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# precisa do manifest do upstream e das tabelas no MESMO DuckDB:
#   1) rode a ingestão + dbt build do upstream (gera manifest + marts)
#   2) então:
DBT_DUCKDB_PATH=../dbt-toll-analytics/toll_analytics.duckdb \
  .venv/bin/dbt build --profiles-dir .
```

## Pré-requisitos
- O projeto upstream `dbt-toll-analytics` construído (manifest em `target/` + marts
  no DuckDB compartilhado). Em produção (dbt Cloud) o cross-project ref é nativo e o
  `--defer` aponta para o warehouse de prod.
