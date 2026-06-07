"""DAG de MANUTENÇÃO — demonstra Sensors e Setup/Teardown tasks.

- Sensor (@task.sensor): espera a tabela de auditoria existir antes de seguir
  (padrão "aguardar estado externo", em vez de assumir que o dado está pronto).
- Setup/Teardown (Airflow 2.7+): cria um schema de scratch (setup) e o derruba
  (teardown) — o teardown roda MESMO se a tarefa do meio falhar, garantindo que
  não fica lixo. É o jeito certo de gerenciar recurso efêmero num DAG.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.sensors.base import PokeReturnValue

from include.callbacks import notify_failure
from include.constants import AUDIT_DATASET, DBT_DUCKDB_PATH, DEFAULT_ARGS, DUCKDB_POOL


@dag(
    dag_id="toll_analytics_maintenance",
    description="Sensor + setup/teardown sobre o DuckDB da auditoria.",
    schedule=[AUDIT_DATASET],  # roda quando a auditoria é atualizada (data-aware)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    on_failure_callback=notify_failure,
    tags=["maintenance", "sensor", "setup-teardown", "duckdb"],
    doc_md=__doc__,
)
def toll_analytics_maintenance():
    @task.sensor(poke_interval=15, timeout=300, mode="poke", pool=DUCKDB_POOL)
    def wait_for_audit() -> PokeReturnValue:
        """SENSOR: aguarda a tabela audit_suspect_transactions existir."""
        import os

        import duckdb

        if not os.path.exists(DBT_DUCKDB_PATH):
            return PokeReturnValue(is_done=False)
        con = duckdb.connect(DBT_DUCKDB_PATH, read_only=True)
        try:
            n = con.execute(
                "select count(*) from information_schema.tables "
                "where table_name = 'audit_suspect_transactions'"
            ).fetchone()[0]
        finally:
            con.close()
        return PokeReturnValue(is_done=bool(n))

    @task(pool=DUCKDB_POOL)
    def setup_scratch() -> None:
        """SETUP: cria o schema de scratch (recurso efêmero da run)."""
        import duckdb

        con = duckdb.connect(DBT_DUCKDB_PATH)
        con.execute("create schema if not exists qa_scratch")
        con.close()

    @task(pool=DUCKDB_POOL)
    def summarize() -> None:
        """Trabalho: materializa um resumo da auditoria no scratch."""
        import duckdb

        con = duckdb.connect(DBT_DUCKDB_PATH)
        con.execute(
            "create or replace table qa_scratch.audit_summary as "
            "select audit_flag, count(*) as n "
            "from main.audit_suspect_transactions group by 1"
        )
        con.close()

    @task(pool=DUCKDB_POOL)
    def teardown_scratch() -> None:
        """TEARDOWN: derruba o scratch (roda mesmo se 'summarize' falhar)."""
        import duckdb

        con = duckdb.connect(DBT_DUCKDB_PATH)
        con.execute("drop schema if exists qa_scratch cascade")
        con.close()

    setup = setup_scratch()
    teardown = teardown_scratch()
    wait_for_audit() >> setup >> summarize() >> teardown
    # pareia teardown↔setup: tudo entre eles fica no escopo de setup/teardown
    teardown.as_teardown(setups=setup)


toll_analytics_maintenance()
