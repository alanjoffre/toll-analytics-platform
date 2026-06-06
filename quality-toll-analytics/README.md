# quality-toll-analytics — Data Quality independente (Soda Core)

Camada de **DQ independente do dbt** com **[Soda Core](https://www.soda.io/)** — uma
"segunda opinião" sobre os marts, rodando direto no DuckDB. Complementa (não substitui)
os testes do dbt, o dbt_expectations e o Elementary: ferramentas diferentes, mesma meta.

```
DuckDB (marts do dbt)  ──[soda scan]──▶  checks/marts.yml  ──▶  PASS / FAIL (gate)
```

## O que checa ([checks/marts.yml](checks/marts.yml))
- `fct_toll_transactions`: `row_count > 0`, `duplicate_count(transaction_id) = 0`,
  `missing_count(transaction_id) = 0`.
- `audit_suspect_transactions`: `invalid_count(audit_flag) = 0` (valores válidos).

## Rodar
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DBT_DUCKDB_PATH=../dbt-toll-analytics/toll_analytics.duckdb \
  .venv/bin/soda scan -d toll_analytics -c configuration.yml checks/marts.yml
# -> "4/4 checks PASSED"
```

## Onde encaixa
- **Gate no Airflow:** task `quality_gate_soda` no `toll_analytics_pipeline` roda o
  `soda scan` **depois** do transform — falha o pipeline se a DQ quebrar.
- **CI:** validado no workflow `governance_ci.yml` (build → soda → mesh).

## Notas honestas (local/DuckDB)
- Python 3.12 removeu o `distutils`; o Soda ainda o usa → shim via `setuptools<81`.
- O Soda fixa `duckdb<1.1`, mas o arquivo é escrito por duckdb 1.5.x → fixamos
  `duckdb>=1.5,<1.6` (override consciente). Em warehouses cloud (Snowflake/BigQuery/
  Databricks), o Soda é nativo e essas fricções de versão não existem.
