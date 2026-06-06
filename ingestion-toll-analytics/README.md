# ingestion-toll-analytics

Camada de **ingestão (EL)** com **[dlt](https://dlthub.com)** — o "E" e o "L" do
ELT, antes do "T" (dbt). Lê os arquivos de **landing** (`data/*.csv`, tratados como
arquivos que "caem" de um sistema upstream) e carrega no schema **`landing`** do
DuckDB. O dbt então consome via `source('toll_raw', ...)`.

```
data/*.csv  ──[dlt]──▶  DuckDB schema `landing`  ──[dbt source()]──▶  staging → ... → marts
```

## O que demonstra
- **EL real** (não só seeds): extract de arquivos + load no warehouse.
- **Disposições de escrita**: `merge` (idempotente por `primary_key`, dedup) para
  transações/entidades; `replace` (full reload) para a dim de tarifa.
- **Metadados de carga** do dlt (`_dlt_load_id`, `_dlt_loads`) — rastreabilidade.
- **Normalização de EL**: campo vazio do CSV (`''`) vira **NULL** (ausente).
- **Reprodutível offline**: lê CSVs commitados, não uma API externa.

## Rodar
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python toll_ingestion.py          # -> schema landing no DuckDB do dbt
```
Por padrão grava no DuckDB do projeto dbt (`../dbt-toll-analytics/toll_analytics.duckdb`);
sobrescreva com `DBT_DUCKDB_PATH` (a orquestração aponta para um arquivo em `/tmp`).

## Onde encaixa
- **Orquestração:** o DAG `toll_analytics_pipeline` roda `ingest_landing` (este dlt)
  **antes** do transform (Cosmos). Ver `../airflow-toll-analytics`.
- **CI:** os workflows de dbt rodam `dlt → dbt build`.
- **Decisão:** ADR-28 (e ADR-13) em `../dbt-toll-analytics`.

> Em produção, os CSVs dariam lugar a conectores reais do dlt (APIs/DB/SaaS) ou a
> ingestão nativa do warehouse (Auto Loader / COPY INTO no Databricks). Os modelos
> dbt a jusante não mudam — só a fonte.
