"""Caminhos e configuração central da camada de orquestração.

Tudo é resolvido por variável de ambiente com fallback calculado a partir da
posição deste arquivo, então funciona tanto LOCAL (venv) quanto em DOCKER
(onde os caminhos são sobrescritos pelo docker-compose).

Princípio: o Airflow NÃO instala dbt no próprio ambiente — ele chama o dbt do
venv do projeto dbt (DBT_EXECUTABLE_PATH). Isso evita conflito de dependências
entre Airflow e dbt e mantém UMA fonte de verdade do dbt.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

# airflow-toll-analytics/include/constants.py -> sobe 2 níveis = airflow-toll-analytics/
AIRFLOW_PROJECT_DIR = Path(__file__).resolve().parents[1]
# raiz do workspace (onde ficam, lado a lado, o projeto dbt e o de airflow)
REPO_ROOT = AIRFLOW_PROJECT_DIR.parent

# --- Projeto dbt -----------------------------------------------------------
DBT_PROJECT_DIR = Path(
    os.getenv("DBT_PROJECT_DIR", str(REPO_ROOT / "dbt-toll-analytics"))
).resolve()

# Executável do dbt: por padrão o do venv do PRÓPRIO projeto dbt.
DBT_EXECUTABLE_PATH = os.getenv(
    "DBT_EXECUTABLE_PATH", str(DBT_PROJECT_DIR / ".venv" / "bin" / "dbt")
)

# profiles.yml mora na raiz do projeto dbt (profiles-dir = a própria pasta).
DBT_PROFILES_DIR = Path(os.getenv("DBT_PROFILES_DIR", str(DBT_PROJECT_DIR))).resolve()
DBT_PROFILE_NAME = os.getenv("DBT_PROFILE_NAME", "toll_analytics")

# Ambiente alvo: 'dev' (default) ou 'prod' — mesma lógica do profiles.yml do dbt.
DBT_TARGET = os.getenv("DBT_TARGET", "dev")

# Pool do Airflow com 1 slot para SERIALIZAR o acesso ao DuckDB (single-writer).
# Garantia real de não-concorrência, independente do executor (ADR-A2). O pool é
# criado no setup (scripts/validate_local.sh e airflow-init do docker-compose).
DUCKDB_POOL = os.getenv("DUCKDB_POOL", "duckdb_serial")

# Caminho do DuckDB nas runs de orquestração: LOCAL (/tmp), não o do projeto no
# OneDrive. Evita lag de lock em filesystem sincronizado e isola a run do banco
# de dev. Lido pelo profiles.yml do dbt via env_var('DBT_DUCKDB_PATH').
DBT_DUCKDB_PATH = os.getenv("DBT_DUCKDB_PATH", "/tmp/toll_analytics_airflow.duckdb")
os.environ.setdefault("DBT_DUCKDB_PATH", DBT_DUCKDB_PATH)

# manifest.json já gerado pelo dbt (build/parse). Usar o manifest deixa o parse
# do DAG rápido e independente de invocar dbt em tempo de parse.
DBT_MANIFEST_PATH = Path(
    os.getenv("DBT_MANIFEST_PATH", str(DBT_PROJECT_DIR / "target" / "manifest.json"))
).resolve()

# --- default_args compartilhados pelos DAGs --------------------------------
# Retries com backoff exponencial: prática de produção para falhas transitórias.
DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": int(os.getenv("AIRFLOW_TASK_RETRIES", "2")),
    "retry_delay": timedelta(minutes=int(os.getenv("AIRFLOW_RETRY_DELAY_MIN", "2"))),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
    # email_on_failure fica a cargo do callback (include/callbacks.py).
    "email_on_failure": False,
    "email_on_retry": False,
}
