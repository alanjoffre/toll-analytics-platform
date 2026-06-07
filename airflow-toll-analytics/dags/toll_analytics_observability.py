"""DAG de OBSERVABILIDADE de dados (agendado, separado do pipeline de PR).

Por que separado (ADR-A3): a detecção de anomalia do Elementary
(volume_anomalies) só é significativa com HISTÓRICO acumulado de várias
execuções e, no adapter dbt-duckdb, emite ruído de transação. Logo, NÃO entra
no pipeline crítico — roda aqui, num cadência própria, onde o baseline acumula.

Entrega:
- roda os testes marcados com a tag 'observability' (anomalia de volume);
- gera o relatório do Elementary (`edr report`) quando o CLI estiver instalado
  (tolerante: a ausência do CLI não derruba o DAG).
"""

from __future__ import annotations

import os
from datetime import datetime

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

from include.callbacks import notify_failure
from include.constants import (
    DBT_EXECUTABLE_PATH,
    DBT_PROFILES_DIR,
    DBT_PROJECT_DIR,
    DBT_TARGET,
    DEFAULT_ARGS,
    DUCKDB_POOL,
)

_dbt_env = {**os.environ, "DBT_TARGET": DBT_TARGET}
_flags = f"--profiles-dir {DBT_PROFILES_DIR} --target {DBT_TARGET}"

with DAG(
    dag_id="toll_analytics_observability",
    description="Testes de anomalia (Elementary) + relatório de observabilidade.",
    default_args=DEFAULT_ARGS,
    schedule=os.getenv("TOLL_OBSERVABILITY_SCHEDULE", "0 7 * * *"),  # após o pipeline
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    on_failure_callback=notify_failure,
    tags=["dbt", "duckdb", "elementary", "observability"],
    doc_md=__doc__,
) as dag:
    # 1) Testes de anomalia (tag:observability) — excluídos do pipeline crítico
    anomaly_tests = BashOperator(
        task_id="anomaly_tests",
        bash_command=(
            f"'{DBT_EXECUTABLE_PATH}' test --select tag:observability {_flags}"
        ),
        cwd=str(DBT_PROJECT_DIR),
        env=_dbt_env,
        append_env=False,
        pool=DUCKDB_POOL,
    )

    # 2) Relatório Elementary (edr). Tolerante: se o CLI não estiver instalado,
    #    apenas registra e segue (não falha o DAG).
    elementary_report = BashOperator(
        task_id="elementary_report",
        bash_command=(
            "if command -v edr >/dev/null 2>&1; then "
            f"edr report --project-dir '{DBT_PROJECT_DIR}' "
            f"--profiles-dir '{DBT_PROFILES_DIR}'; "
            "else echo '[obs] edr (elementary-data CLI) não instalado — pulando relatório.'; "
            "fi"
        ),
        cwd=str(DBT_PROJECT_DIR),
        env=_dbt_env,
        append_env=False,
        pool=DUCKDB_POOL,
    )

    anomaly_tests >> elementary_report
