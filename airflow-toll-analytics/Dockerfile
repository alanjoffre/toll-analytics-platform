# Imagem de produção do Airflow + Cosmos, com o dbt num venv ISOLADO (ADR-A1).
FROM apache/airflow:2.10.5-python3.12

# --- Camada Airflow (orquestração) -----------------------------------------
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir \
      "apache-airflow==2.10.5" \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.12.txt" \
 && pip install --no-cache-dir -r /requirements.txt

# --- Camada dbt (venv isolado para o Cosmos chamar via subprocess) ---------
USER root
RUN python -m venv /opt/dbt-venv \
 && /opt/dbt-venv/bin/pip install --no-cache-dir "dbt-duckdb>=1.8,<2.0" "elementary-data"
RUN chown -R airflow: /opt/dbt-venv
USER airflow

# Caminhos dentro do container (sobrescrevem os defaults de include/constants.py)
ENV DBT_EXECUTABLE_PATH=/opt/dbt-venv/bin/dbt \
    DBT_PROJECT_DIR=/opt/airflow/dbt-toll-analytics \
    DBT_PROFILES_DIR=/opt/airflow/dbt-toll-analytics \
    PYTHONPATH=/opt/airflow
