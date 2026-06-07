# Guia passo a passo — dbt + Airflow (toll-analytics-platform)

Guia **didático + operacional**: o que cada projeto faz, **como funciona por dentro**
(passo a passo) e os **comandos do dia a dia**. Pensado para você (a) entender o todo e
(b) aplicar no trabalho. Domínio: auditoria de vale-pedágio (dados sintéticos).

> Visão de plataforma (do dado cru ao consumo):
> ```
> arquivos/Kafka ─► dlt (EL) ─► DuckDB(landing) ─► dbt (staging→intermediate→marts)
>                                                      │
>                          Airflow orquestra ──────────┘──► Soda (DQ) ─► BI (Evidence)
> ```

---

# PARTE 1 — dbt (transformação · `dbt-toll-analytics/`)

## 1.1 O que o dbt faz (em 1 parágrafo)
dbt é o **"T" do ELT**: você escreve **SELECTs em arquivos `.sql`** (chamados *models*) e o
dbt os transforma em tabelas/views no banco, **na ordem certa**, com **testes**,
**documentação** e **lineage**. Você versiona SQL como software (Git, testes, CI).

## 1.2 Vocabulário essencial (o mínimo para ler o projeto)
| Conceito | O que é | Onde no projeto |
|---|---|---|
| **model** | 1 arquivo `.sql` = 1 `SELECT` → vira view/tabela | `models/staging/stg_*.sql`, `models/marts/*.sql` |
| **`ref()`** | referência a outro model → cria o **DAG** e a ordem | `from {{ ref('stg_toll_transactions') }}` |
| **`source()`** | tabela de entrada (bronze/landing) | `from {{ source('toll_raw', 'raw_toll_transactions') }}` |
| **materialization** | como o model vira objeto: `view` / `table` / `incremental` / `ephemeral` | staging=view, marts=table, fct=incremental |
| **test** | asserção sobre os dados (genérico) ou a lógica (unit test) | `_*.yml` + `models/marts/_unit_tests.yml` |
| **macro** | função Jinja reutilizável que gera SQL | `macros/audit_flag.sql`, `cents_to_brl.sql` |
| **snapshot** | histórico de mudanças (SCD2) | `snapshots/snap_toll_plazas.sql` |
| **contract** | trava colunas+tipos do model (build quebra se mudar) | `models/marts/_marts.yml` |
| **semantic layer** | métricas governadas (MetricFlow) | `models/marts/_semantic_models.yml` |

## 1.3 Como o projeto está organizado (Medallion)
```
landing (dlt)         staging (silver)        intermediate + marts (gold)
raw_toll_transactions stg_toll_transactions   int_transactions_enriched
raw_toll_plazas       stg_toll_plazas         dim_plaza / dim_vehicle / dim_date
raw_vehicles          stg_vehicles            fct_toll_transactions (incremental)
raw_vehicle_categories stg_vehicle_categories agg_daily_revenue_by_plaza
raw_fare_schedule     stg_fare_schedule       audit_suspect_transactions ◄── PRODUTO
```
- **Silver (staging):** 1 model por fonte — tipagem, limpeza, dedup, masking de PII. Sem join.
- **Gold (intermediate/marts):** enriquece (joins + regra de negócio), modela dimensional
  (fato/dimensões), agrega e entrega a **auditoria** (transações suspeitas).

## 1.4 Passo a passo de UMA execução (`dbt build`)
1. `dbt deps` — instala os packages (dbt_utils, dbt_expectations, elementary, evaluator).
2. **dbt lê o `ref()`/`source()`** de cada model e monta o DAG (grafo de dependências).
3. Constrói **na ordem topológica**: staging → intermediate → marts (+ snapshot).
4. Após cada model (ou no fim), roda os **testes** daquele model.
5. `on-run-end` grava metadados em `_audit_runs` (observabilidade).
6. Verde = `PASS=… ERROR=0`. O `WARN=1` é intencional (cobrança em falha → a auditoria sinaliza).

## 1.5 A técnica-estrela: tarifa **point-in-time**
O preço muda no tempo. Comparar uma transação antiga com a tarifa **atual** gera falso
positivo. A solução é juntar pela **data do evento**: `event_date BETWEEN valid_from AND valid_to`
(em `int_transactions_enriched.sql`). É o que separa júnior (tarifa atual) de sênior.

## 1.6 dbt no dia a dia (os comandos que você mais usa)
```bash
cd dbt-toll-analytics && source .venv/bin/activate   # (ou use os caminhos do .venv)

dbt build --profiles-dir .                 # roda TUDO (run + test + snapshot)
dbt run  --select stg_toll_transactions    # roda 1 model
dbt run  --select stg_toll_transactions+   # esse model + tudo a jusante (+)
dbt run  --select +fct_toll_transactions   # esse model + tudo a montante (+ antes)
dbt test --select audit_suspect_transactions   # só os testes de 1 model
dbt build --select tag:observability       # só o que tem a tag
dbt build --exclude tag:observability      # tudo menos a tag (é o que o CI roda)
dbt docs generate && dbt docs serve        # lineage navegável no navegador
dbt source freshness --profiles-dir .      # SLA de ingestão (frescor)
```
**Adicionar um model novo (receita):**
1. Crie `models/<camada>/meu_model.sql` com `select ... from {{ ref('...') }}`.
2. Documente/teste em `_<camada>.yml` (description + tests).
3. `dbt build --select meu_model+` para validar ele e o downstream.
4. `dbt docs generate` — ele aparece no lineage.

**Debugar:**
```bash
dbt compile --select meu_model    # vê o SQL final (Jinja resolvido) em target/compiled/
dbt show    --select meu_model    # roda e mostra uma amostra
dbt build --select meu_model --no-partial-parse   # ignora cache de parse (quando muda algo)
```
> **Dica (deste repo):** ao mover/renomear pastas, rode com `--no-partial-parse` ou apague
> `target/` — o cache guarda caminhos absolutos. (Foi um bug real que enfrentamos.)

---

# PARTE 2 — Airflow (orquestração · `airflow-toll-analytics/`)

## 2.1 O que o Airflow faz (em 1 parágrafo)
Airflow **agenda e executa pipelines** com dependências, **retries**, alertas e
visibilidade. Aqui ele orquestra o dbt via **Astronomer Cosmos**: cada model/test do dbt
vira **uma task** do Airflow (lineage real), além de rodar a ingestão (dlt) e o gate de DQ.

## 2.2 Vocabulário essencial
| Conceito | O que é | Onde no projeto |
|---|---|---|
| **DAG** | um pipeline (grafo de tasks) | `dags/toll_analytics_pipeline.py` |
| **task / operator** | uma unidade de trabalho (Bash, Python, Cosmos…) | `BashOperator`, `DbtTaskGroup` |
| **schedule** | quando roda (cron / dataset) | `schedule="0 6 * * *"` |
| **retries / backoff** | re-tenta falha transitória | `DEFAULT_ARGS` em `include/constants.py` |
| **pool** | limita concorrência (serializa) | `duckdb_serial` (DuckDB é single-writer) |
| **Dataset** | agendamento orientado a dado | pipeline `outlets=[AUDIT_DATASET]` |
| **TaskFlow (`@task`)** | DAG pythônico + XCom | `dags/toll_analytics_quality_gate.py` |
| **sensor** | espera um estado externo | `wait_for_audit` em `dags/..._maintenance.py` |

## 2.3 Os DAGs do projeto
- **`toll_analytics_pipeline`** (o principal): `ingest_landing` (dlt) → `source_freshness` →
  `transform` (Cosmos: 1 task por model/test) → `quality_gate_soda` → `generate_docs`.
- **`toll_analytics_quality_gate`**: TaskFlow + XCom + dynamic mapping + branching.
- **`toll_analytics_backfill`**: catchup; passa a data lógica (`{{ ds }}`) ao dbt como var.
- **`toll_analytics_maintenance`**: sensor + setup/teardown.
- **`toll_analytics_observability`**: testes de anomalia (Elementary), agendado.

## 2.4 Passo a passo de UMA execução do pipeline
1. O **scheduler** dispara a run (no horário) — ou você roda manual.
2. `ingest_landing`: o **dlt** lê os arquivos de landing → schema `landing` no DuckDB.
3. `source_freshness`: confere o SLA da fonte (WARN não bloqueia; ERROR sim).
4. `transform` (**Cosmos**): builda cada model do dbt como task, na ordem do DAG; testes após.
5. `quality_gate_soda`: **Soda Core** roda checks independentes nos marts (gate).
6. `generate_docs`: gera o `dbt docs` e marca o **Dataset** → dispara DAGs data-aware.

## 2.5 Airflow no dia a dia
```bash
cd airflow-toll-analytics
export AIRFLOW_HOME=/tmp/airflow-toll-analytics-home
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags" PYTHONPATH="$PWD"
# (+ os DBT_* do README; ou use scripts/validate_local.sh que já exporta tudo)

airflow dags list                                  # lista os DAGs
airflow dags list-import-errors                    # erro de import? (1º a checar)
airflow tasks list toll_analytics_pipeline         # tasks de um DAG
airflow dags test toll_analytics_pipeline 2026-05-03   # RODA o DAG ponta a ponta (sem scheduler)
airflow tasks test toll_analytics_pipeline ingest_landing 2026-05-03  # roda 1 task isolada
airflow variables set toll_dbt_target prod         # troca dev↔prod sem editar código
airflow pools set duckdb_serial 1 "serializa DuckDB"
bash scripts/validate_local.sh                     # cria venvs, valida e roda o pipeline
```
**Adicionar um DAG novo:** crie `dags/meu_dag.py`, rode `airflow dags list-import-errors`
(0 erros) e `airflow dags test meu_dag <data>`. O CI (`airflow_ci`) tem um teste de
integridade que falha se algum DAG não importar.

**Backfill (reprocessar histórico):**
```bash
airflow dags backfill toll_analytics_backfill --start-date 2026-05-01 --end-date 2026-05-03
```
> **Dica (deste repo):** `dags test` NÃO honra `pool`/`max_active_tasks` como o scheduler;
> por isso o DuckDB (single-writer) usa pool de 1 slot **e** roda em arquivo local (/tmp) na
> orquestração. Em warehouse (Databricks) isso some — a concorrência é nativa.

---

# PARTE 3 — Como dbt e Airflow se conectam
- **dbt** sabe *como* transformar (SQL + ordem). **Airflow** sabe *quando* e *em que ordem
  macro* rodar (ingestão → transform → DQ → docs), com retry/alerta/agendamento.
- A ponte é o **Cosmos**: ele lê o `manifest.json` do dbt e materializa cada nó como task —
  então o lineage do dbt aparece dentro do Airflow, com retry granular por model.
- **Isolamento (ADR-A1):** o Airflow chama o dbt do **venv do projeto dbt** (subprocess),
  não instala dbt no próprio ambiente. Zero conflito de dependências.

# PARTE 4 — Rotina do dia a dia (resumo de bolso)
```bash
# 1) mexeu num model dbt? valida só o afetado + downstream:
cd dbt-toll-analytics && .venv/bin/dbt build --select meu_model+ --profiles-dir .
# 2) mexeu num DAG? cheque import e rode o DAG:
cd ../airflow-toll-analytics && .venv/bin/airflow dags list-import-errors
.venv/bin/airflow dags test toll_analytics_pipeline 2026-05-03
# 3) antes do commit: pre-commit roda ruff/yaml; o CI confere build + testes + docs
pre-commit run --all-files
# 4) ponta a ponta local (ingestão→transform→DQ→docs):
bash airflow-toll-analytics/scripts/validate_local.sh
```

## Troubleshooting rápido (problemas reais que vimos)
| Sintoma | Causa | Solução |
|---|---|---|
| dbt acha caminho antigo de arquivo | cache de parse (`target/`) | `--no-partial-parse` ou apagar `target/` |
| `Could not set lock ... duckdb` | DuckDB single-writer + concorrência | pool de 1 slot + DuckDB em `/tmp` na orquestração |
| `'' to INT32` no build | campo vazio do CSV vira `''` | normalizar `'' → NULL` na ingestão (dlt) |
| `timestamptz -> DATE` | dlt inferiu timestamptz | carregar como **texto** na landing; tipar no staging |
| provider do Airflow quebra o venv | instalou sem o constraints | sempre `pip install ... --constraint <constraints-2.10.5>` |
| pre-commit "passa" local e falha no CI | leitura defasada (OneDrive) | o **CI é o juiz**; rode `ruff format` na versão fixada antes |

---

> **Referências complementares:** `dbt-toll-analytics/PLANO_DO_PROJETO.md` (o "cérebro"),
> `dbt-toll-analytics/docs/Documentacao_dbt_toll_analytics.docx` (didático, arquivo por
> arquivo + ADRs), e os READMEs de cada projeto. Os **ADRs** registram o *porquê* de cada
> decisão — leia-os para entender o julgamento de engenharia por trás do código.
