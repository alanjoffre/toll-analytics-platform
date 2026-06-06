#!/usr/bin/env bash
# Valida a camada Airflow SEM Docker: instala Airflow+Cosmos num venv dedicado,
# garante o manifest do dbt e roda o pipeline ponta-a-ponta com `airflow dags test`.
#
# Uso:  bash scripts/validate_local.sh [DATA_EXECUCAO]
#       (DATA_EXECUCAO default = 2026-05-03, dentro da janela dos dados sintéticos)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DATE="${1:-2026-05-03}"

# --- caminhos ---------------------------------------------------------------
export AIRFLOW_PROJECT_DIR="$HERE"
export DBT_PROJECT_DIR="${DBT_PROJECT_DIR:-$(cd "$HERE/../dbt-toll-analytics" && pwd)}"
export DBT_EXECUTABLE_PATH="${DBT_EXECUTABLE_PATH:-$DBT_PROJECT_DIR/.venv/bin/dbt}"
export DBT_PROFILES_DIR="${DBT_PROFILES_DIR:-$DBT_PROJECT_DIR}"
export DBT_TARGET="${DBT_TARGET:-dev}"

# AIRFLOW_HOME FORA do OneDrive (evita lock/sync na metadata sqlite)
export AIRFLOW_HOME="${AIRFLOW_HOME:-/tmp/airflow-toll-analytics-home}"
export AIRFLOW__CORE__DAGS_FOLDER="$HERE/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=SequentialExecutor
export PYTHONPATH="$HERE:${PYTHONPATH:-}"

VENV="$HERE/.venv"

echo "==> [1/5] venv do Airflow ($VENV)"
if [ ! -x "$VENV/bin/airflow" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet "apache-airflow==2.10.5" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.12.txt"
  "$VENV/bin/pip" install --quiet -r "$HERE/requirements.txt"
fi
export PATH="$VENV/bin:$PATH"

# venv do projeto de INGESTÃO (a task ingest_landing roda o dlt deste venv)
INGESTION_DIR="${INGESTION_PROJECT_DIR:-$(cd "$HERE/../ingestion-toll-analytics" && pwd)}"
if [ ! -x "$INGESTION_DIR/.venv/bin/python" ]; then
  echo "==> venv da ingestão ($INGESTION_DIR/.venv)"
  python3 -m venv "$INGESTION_DIR/.venv"
  "$INGESTION_DIR/.venv/bin/pip" install --quiet -r "$INGESTION_DIR/requirements.txt"
fi

# venv da QUALIDADE (a task quality_gate_soda roda o `soda` deste venv)
QUALITY_DIR="${QUALITY_PROJECT_DIR:-$(cd "$HERE/../quality-toll-analytics" && pwd)}"
if [ ! -x "$QUALITY_DIR/.venv/bin/soda" ]; then
  echo "==> venv da qualidade ($QUALITY_DIR/.venv)"
  python3 -m venv "$QUALITY_DIR/.venv"
  "$QUALITY_DIR/.venv/bin/pip" install --quiet -r "$QUALITY_DIR/requirements.txt"
fi

echo "==> [2/5] garantir deps + manifest do dbt"
( cd "$DBT_PROJECT_DIR" && "$DBT_EXECUTABLE_PATH" deps --profiles-dir . >/dev/null \
  && "$DBT_EXECUTABLE_PATH" parse --profiles-dir . >/dev/null )

echo "==> [3/5] inicializar metadata do Airflow + pool de serialização do DuckDB"
airflow db migrate >/dev/null 2>&1
airflow pools set "${DUCKDB_POOL:-duckdb_serial}" 1 "Serializa acesso ao DuckDB (single-writer)" >/dev/null

echo "==> [4/5] checar erros de import dos DAGs (deve ser vazio)"
airflow dags list-import-errors
echo "DAGs detectados:"
airflow dags list 2>/dev/null | grep -E "toll_analytics" || true

echo "==> [5/5] rodar o pipeline ponta-a-ponta (airflow dags test) em $RUN_DATE"
airflow dags test toll_analytics_pipeline "$RUN_DATE"

echo "==> OK. Validação concluída."
