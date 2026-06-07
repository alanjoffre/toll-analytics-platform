"""DAG de BACKFILL por data — liga o data_interval do Airflow ao dbt.

Demonstra o padrão time-partitioned: cada run carrega a SUA data, passando a
data lógica ({{ ds }}) ao dbt como --vars. Com catchup=True, o Airflow cria uma
run por dia do intervalo [start_date, end_date) — é assim que se faz reprocesso
histórico (backfill) determinístico e idempotente.

Em produção (Databricks), esse run_date alimentaria a estratégia incremental
microbatch (event_time/batch). No DuckDB de dev a var é informativa (o fato usa
lookback), mas o WIRING Airflow→dbt é real e validado.

Backfill de verdade (scheduler):  airflow dags backfill toll_analytics_backfill \
    --start-date 2026-05-01 --end-date 2026-05-03
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
    dag_id="toll_analytics_backfill",
    description="Backfill time-partitioned: data lógica da run -> dbt --vars.",
    schedule="@daily",
    start_date=datetime(2026, 5, 1),
    end_date=datetime(2026, 5, 4),
    catchup=True,  # cria 1 run por dia do intervalo (backfill)
    max_active_runs=1,  # serial: DuckDB é single-writer (ADR-A2)
    default_args=DEFAULT_ARGS,
    on_failure_callback=notify_failure,
    tags=["dbt", "duckdb", "backfill", "time-partitioned"],
    doc_md=__doc__,
) as dag:
    # {{ ds }} (data lógica da run) entra como var do dbt. NÃO é f-string para o
    # Jinja do Airflow renderizar {{ ds }} em runtime.
    dbt_run_for_date = BashOperator(
        task_id="dbt_run_for_date",
        bash_command=(
            "'"
            + DBT_EXECUTABLE_PATH
            + "' run --select stg_toll_transactions "
            + _flags
            + " --vars '{run_date: \"{{ ds }}\"}'"
        ),
        cwd=str(DBT_PROJECT_DIR),
        env=_dbt_env,
        append_env=False,
        pool=DUCKDB_POOL,
    )
