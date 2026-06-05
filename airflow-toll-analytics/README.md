# airflow-toll-analytics

Camada de **orquestração (Apache Airflow + Astronomer Cosmos)** sobre o projeto
[`dbt-toll-analytics`](../dbt-toll-analytics). O Cosmos transforma **cada nó do
dbt (model, seed, snapshot, test) em uma task do Airflow**, preservando o
lineage — não é um `dbt build` monolítico num operador só.

```
source_freshness ──▶ [ transform (Cosmos: 1 task por nó do dbt) ] ──▶ generate_docs
   (gate de             stg_* ▶ int_* ▶ dim_*/fct_* ▶ agg_*/audit_*        (lineage
    ingestão)           + testes de cada model logo após (AFTER_EACH)       navegável)
```

## Por que Cosmos (e não um BashOperator único)
- **Lineage real & retry granular:** se `fct_toll_transactions` falhar, só ele e o
  downstream re-rodam — não o pipeline inteiro.
- **Testes como tasks:** a falha de um teste do dbt corta o fluxo (gate de qualidade).
- **Observabilidade no Airflow:** cada model/test aparece no grid/graph do Airflow.

## O que esta camada entrega (mapa "recurso do Airflow → onde está")
| Recurso | Onde |
|---|---|
| Agendamento (cron) + `catchup`/backfill | `schedule`, `start_date`, `catchup` em [dags/toll_analytics_pipeline.py](dags/toll_analytics_pipeline.py) |
| Lineage dbt → tasks (1 nó = 1 task) | `DbtTaskGroup` + `TestBehavior.AFTER_ALL` |
| Gate de ingestão (freshness) | task `source_freshness` |
| Qualidade (testes do dbt cortam o fluxo) | tasks de teste do Cosmos |
| Documentação / lineage | task `generate_docs` (`dbt docs generate`) |
| Retries + backoff exponencial | `DEFAULT_ARGS` em [include/constants.py](include/constants.py) |
| SLA + `dagrun_timeout` | `default_args["sla"]`, `dagrun_timeout` |
| Alerta on-failure (log + Slack opcional) | [include/callbacks.py](include/callbacks.py) |
| Separação dev/prod | `DBT_TARGET` (env) → `ProfileConfig.target_name` |
| Observabilidade de dados (anomalia) | DAG [dags/toll_analytics_observability.py](dags/toll_analytics_observability.py) |
| Concorrência segura no DuckDB | `max_active_tasks=1` (ADR-A2) |
| Isolamento de dependências (Airflow × dbt) | `DBT_EXECUTABLE_PATH` (ADR-A1) |
| Teste de integridade de DAG (CI) | [tests/test_dag_integrity.py](tests/test_dag_integrity.py) + [.github/workflows/airflow_ci.yml](.github/workflows/airflow_ci.yml) |
| Empacotamento de produção | [Dockerfile](Dockerfile) + [docker-compose.yml](docker-compose.yml) |

## Decisões de design (ADR)
- **ADR-A1 — dbt fora do ambiente do Airflow.** O Airflow chama o dbt do venv do
  próprio projeto dbt (`DBT_EXECUTABLE_PATH`), via subprocess. Evita o conflito
  clássico de pins entre Airflow e dbt e mantém uma única fonte de verdade do dbt.
- **ADR-A2 — `max_active_tasks=1`.** DuckDB é *single-writer* (1 arquivo). Serializar
  as tasks evita lock/corrupção. Em Databricks/warehouse o paralelismo é liberado.
- **ADR-A3 — observabilidade isolada.** Os testes de anomalia (Elementary) rodam no
  DAG `toll_analytics_observability`, não no pipeline crítico (precisam de histórico
  e geram ruído de transação no dbt-duckdb).

## Como rodar

### Opção A — Local, sem Docker (validação rápida)
```bash
bash scripts/validate_local.sh            # instala venv, valida e roda dags test
# ou com uma data específica dentro da janela dos dados sintéticos:
bash scripts/validate_local.sh 2026-05-03
```
O script cria `./.venv`, garante o `manifest.json` do dbt, checa erros de import e
executa `airflow dags test toll_analytics_pipeline` ponta-a-ponta.

### Opção B — Docker (production-realistic)
```bash
cp .env.example .env
docker compose up -d --build                      # webserver em http://localhost:8080 (admin/admin)
docker compose run --rm airflow-cli \
  airflow dags test toll_analytics_pipeline 2026-05-03
docker compose down -v
```

## Pré-requisitos
- O projeto `dbt-toll-analytics` ao lado desta pasta, com seu venv em `.venv/`
  (ou ajuste `DBT_*` no `.env`). Em Docker, o dbt é instalado num venv isolado na
  imagem e o projeto é montado como volume.
