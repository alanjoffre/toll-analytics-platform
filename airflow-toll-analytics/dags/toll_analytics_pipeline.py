"""DAG principal: orquestra o produto de dados de pedágio (dbt) com Cosmos.

O que este DAG entrega (o "tudo o que o Airflow oferece" aplicado ao dbt):
- LINEAGE REAL: cada model/seed/snapshot/test do dbt vira UMA task no Airflow
  (via Astronomer Cosmos), com as dependências derivadas do DAG do dbt.
- GATE DE INGESTÃO: roda `dbt source freshness` antes de transformar.
- QUALIDADE: os testes do dbt rodam como tasks; falha de teste interrompe o
  fluxo downstream (dependência do Airflow).
- DOCUMENTAÇÃO: gera o `dbt docs` (catalog + manifest) ao final.
- CONFIABILIDADE: retries com backoff, SLA, timeout de DAG, alerta on_failure.
- AGENDAMENTO + BACKFILL: schedule cron, start_date, catchup configurável.

Decisões de design (ADR):
- ADR-A1: o Airflow NÃO tem dbt instalado; chama o dbt do venv do projeto dbt
  (DBT_EXECUTABLE_PATH). Zero conflito de dependências, uma fonte de verdade.
- ADR-A2: max_active_tasks=1. O DuckDB é single-writer (1 arquivo); serializar
  as tasks evita corrupção/lock. Em Databricks/warehouse isso não é necessário
  e o paralelismo seria liberado.
- ADR-A3: testes com tag 'observability' (anomalia Elementary) são EXCLUÍDOS
  aqui e rodam no DAG dedicado toll_analytics_observability.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

from cosmos import (
    DbtTaskGroup,
    ExecutionConfig,
    ProfileConfig,
    ProjectConfig,
    RenderConfig,
)
from cosmos.constants import ExecutionMode, InvocationMode, TestBehavior

from include.callbacks import notify_failure, notify_sla_miss
from include.constants import (
    DBT_EXECUTABLE_PATH,
    DBT_MANIFEST_PATH,
    DBT_PROFILE_NAME,
    DBT_PROFILES_DIR,
    DBT_PROJECT_DIR,
    DBT_TARGET,
    DEFAULT_ARGS,
    DUCKDB_POOL,
)

# --- Configuração do Cosmos -------------------------------------------------
profile_config = ProfileConfig(
    profile_name=DBT_PROFILE_NAME,
    target_name=DBT_TARGET,
    profiles_yml_filepath=DBT_PROFILES_DIR / "profiles.yml",
)

# Usa o manifest.json já gerado quando existir (parse rápido); senão, o Cosmos
# faz `dbt ls` em tempo de parse (precisa de deps instaladas no projeto dbt).
_project_kwargs = {"dbt_project_path": DBT_PROJECT_DIR, "project_name": "toll_analytics"}
if DBT_MANIFEST_PATH.exists():
    _project_kwargs["manifest_path"] = DBT_MANIFEST_PATH
project_config = ProjectConfig(**_project_kwargs)

execution_config = ExecutionConfig(
    execution_mode=ExecutionMode.LOCAL,
    # SUBPROCESS: o Cosmos chama o dbt do venv do projeto dbt como subprocesso,
    # em vez de importar o dbt no ambiente do Airflow (ADR-A1).
    invocation_mode=InvocationMode.SUBPROCESS,
    dbt_executable_path=DBT_EXECUTABLE_PATH,
)

render_config = RenderConfig(
    # Caminho crítico = só o NOSSO projeto. Exclui (ADR-A3):
    #  - tag:observability  -> testes de anomalia (rodam no DAG de observabilidade)
    #  - package:elementary -> models internos de plumbing do Elementary
    exclude=["tag:observability", "package:elementary"],
    # AFTER_ALL: constrói TODOS os models e só então roda os testes. Necessário
    # num DB limpo (first-run): testes de relationship referenciam tabelas de
    # OUTROS models; AFTER_EACH poderia rodá-los antes da tabela referenciada
    # existir. AFTER_ALL garante a ordem correta. (Os models seguem 1 task cada.)
    test_behavior=TestBehavior.AFTER_ALL,
    # Airflow 2.10 + SQLite (dags test) quebra ao materializar dataset aliases do
    # Cosmos; desligamos a emissão de datasets (não usamos scheduling por dataset).
    emit_datasets=False,
)

# Ambiente passado ao dbt em cada chamada (BashOperators de freshness/docs)
_dbt_env = {**os.environ, "DBT_TARGET": DBT_TARGET}
_dbt_common_flags = f"--profiles-dir {DBT_PROFILES_DIR} --target {DBT_TARGET}"

with DAG(
    dag_id="toll_analytics_pipeline",
    description="Pipeline diário de analytics + auditoria de pedágio (dbt via Cosmos).",
    default_args={**DEFAULT_ARGS, "sla": timedelta(hours=1)},
    schedule=os.getenv("TOLL_PIPELINE_SCHEDULE", "0 6 * * *"),  # diário 06:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,  # ADR-A2: DuckDB é single-writer
    dagrun_timeout=timedelta(hours=2),
    on_failure_callback=notify_failure,
    sla_miss_callback=notify_sla_miss,
    tags=["dbt", "duckdb", "cosmos", "toll", "analytics"],
    doc_md=__doc__,
) as dag:

    # 1) GATE: contrato de ingestão (frescor da fonte). WARN não bloqueia; ERROR sim.
    source_freshness = BashOperator(
        task_id="source_freshness",
        bash_command=f"'{DBT_EXECUTABLE_PATH}' source freshness {_dbt_common_flags}",
        cwd=str(DBT_PROJECT_DIR),
        env=_dbt_env,
        append_env=False,
        pool=DUCKDB_POOL,
    )

    # 2) TRANSFORMAÇÃO + TESTES: cada nó do dbt = 1 task (lineage real via Cosmos).
    #    pool=DUCKDB_POOL (1 slot) serializa o acesso ao DuckDB (ADR-A2).
    transform = DbtTaskGroup(
        group_id="transform",
        project_config=project_config,
        profile_config=profile_config,
        execution_config=execution_config,
        render_config=render_config,
        operator_args={"pool": DUCKDB_POOL},
    )

    # 3) DOCUMENTAÇÃO: lineage navegável (manifest + catalog)
    generate_docs = BashOperator(
        task_id="generate_docs",
        bash_command=f"'{DBT_EXECUTABLE_PATH}' docs generate {_dbt_common_flags}",
        cwd=str(DBT_PROJECT_DIR),
        env=_dbt_env,
        append_env=False,
        pool=DUCKDB_POOL,
    )

    source_freshness >> transform >> generate_docs
