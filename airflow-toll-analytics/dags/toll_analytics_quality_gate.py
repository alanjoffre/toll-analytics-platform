"""DAG de QUALITY GATE — demonstra TaskFlow API, XCom, Dynamic Task Mapping e Branching.

Lê o resultado do pipeline (audit_suspect_transactions) e, por praça, verifica se
o número de suspeitas passou de um limiar. Se alguma praça estourar, ramifica para
um alerta; senão, segue limpo.

Conceitos do Airflow exercitados:
- TaskFlow API (@dag/@task): DAG pythônico, sem operadores explícitos.
- XCom: o retorno de um @task vira entrada do próximo automaticamente.
- Dynamic Task Mapping (.expand): 1 task POR praça, geradas em runtime.
- Branching (@task.branch): caminho condicional (alerta x limpo).

Acionamento: por DATASET (após o pipeline) — ver toll_analytics_pipeline — ou manual.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.operators.empty import EmptyOperator

from include.callbacks import notify_failure
from include.constants import AUDIT_DATASET, DBT_DUCKDB_PATH, DEFAULT_ARGS, DUCKDB_POOL

# limiar de suspeitas por praça acima do qual disparamos alerta
SUSPECT_THRESHOLD = int(os.getenv("SUSPECT_PLAZA_THRESHOLD", "2"))

log = logging.getLogger("toll_analytics.quality_gate")


@dag(
    dag_id="toll_analytics_quality_gate",
    description="Quality gate por praça (TaskFlow + XCom + mapping + branching).",
    schedule=[AUDIT_DATASET],  # DATA-AWARE: roda quando o pipeline atualiza o dataset
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    on_failure_callback=notify_failure,
    tags=["taskflow", "quality", "duckdb"],
    doc_md=__doc__,
)
def toll_analytics_quality_gate():
    @task(pool=DUCKDB_POOL)
    def suspects_by_plaza() -> list[dict]:
        """XCom-source: lê suspeitas por praça do DuckDB (read-only)."""
        import duckdb

        con = duckdb.connect(DBT_DUCKDB_PATH, read_only=True)
        try:
            rows = con.execute(
                "select plaza_id, count(*) as suspects "
                "from main.audit_suspect_transactions group by 1 order by 1"
            ).fetchall()
        finally:
            con.close()
        return [{"plaza_id": r[0], "suspects": int(r[1])} for r in rows]

    @task
    def check_plaza(item: dict) -> dict:
        """Mapeada dinamicamente: 1 instância por praça (.expand)."""
        item = {**item, "breached": item["suspects"] > SUSPECT_THRESHOLD}
        log.info(
            "Praça %s: %s suspeitas (limiar %s) -> breached=%s",
            item["plaza_id"],
            item["suspects"],
            SUSPECT_THRESHOLD,
            item["breached"],
        )
        return item

    @task.branch
    def decide(results: list[dict]) -> str:
        """Branching: alerta se alguma praça estourou; senão segue limpo."""
        breached = [r for r in results if r["breached"]]
        return "alert_high_suspicion" if breached else "all_clear"

    @task
    def alert_high_suspicion(results: list[dict]) -> None:
        bad = [r for r in results if r["breached"]]
        log.warning("ALERTA — praças acima do limiar de suspeita: %s", bad)

    all_clear = EmptyOperator(task_id="all_clear")

    counts = suspects_by_plaza()
    checked = check_plaza.expand(item=counts)  # DYNAMIC TASK MAPPING
    decide(checked) >> [alert_high_suspicion(checked), all_clear]


toll_analytics_quality_gate()
