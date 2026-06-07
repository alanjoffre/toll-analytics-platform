"""Ingestão (EL) com dlt — arquivos de landing (CSV) → DuckDB schema `landing`.

Simula o padrão real "arquivos caem de um sistema upstream → extract+load no
warehouse": o dlt lê os CSVs de `data/` (tratados como landing files) e carrega
no DuckDB, com tipagem/normalização, METADADOS de carga (_dlt_load_id, _dlt_loads)
e disposições de escrita:
  - merge (idempotente por primary_key) para fatos/entidades com chave;
  - replace (full reload) para dimensões pequenas sem PK natural única.

O dbt consome essas tabelas via `source('toll_raw', ...)` (ver _sources.yml),
substituindo os antigos seeds — é o ADR-13 realizado. Continua reprodutível
offline porque o dlt lê CSVs commitados (não uma API externa).

Rodar:  python toll_ingestion.py
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import dlt

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("TOLL_LANDING_DIR", str(HERE / "data")))

# Mesmo DuckDB que o dbt lê: dev = arquivo do projeto dbt; orquestração = DBT_DUCKDB_PATH.
DUCKDB_PATH = os.getenv(
    "DBT_DUCKDB_PATH",
    str(HERE.parent / "dbt-toll-analytics" / "toll_analytics.duckdb"),
)

# (nome do arquivo/tabela, primary_key | None, column hints)
# Landing = RAW como TEXTO (schema-on-read): a tipagem é responsabilidade do
# staging (silver). Forçar event_ts a texto evita o dlt inferir TIMESTAMPTZ — que
# o DuckDB não casta direto para DATE no join point-in-time.
SOURCES = [
    ("raw_toll_transactions", "transaction_id", {"event_ts": {"data_type": "text"}}),
    ("raw_toll_plazas", "plaza_id", None),
    ("raw_vehicles", "vehicle_id", None),
    ("raw_vehicle_categories", "category", None),
    ("raw_fare_schedule", None, None),  # replace: dim de tarifa (sem PK única)
]


def _read_csv(name: str):
    # Normalização de EL: campo vazio do CSV ('') => NULL (ausente). Evita que o
    # '' chegue ao warehouse e quebre casts a jusante; é responsabilidade do EL.
    with open(DATA_DIR / f"{name}.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield {k: (v if v != "" else None) for k, v in row.items()}


@dlt.source(name="toll_raw")
def toll_raw_source():
    for name, pk, cols in SOURCES:
        yield dlt.resource(
            _read_csv(name),
            name=name,
            write_disposition="merge" if pk else "replace",
            primary_key=pk,
            columns=cols,
        )


def run():
    pipeline = dlt.pipeline(
        pipeline_name="toll_ingestion",
        destination=dlt.destinations.duckdb(DUCKDB_PATH),
        dataset_name="landing",
    )
    info = pipeline.run(toll_raw_source())
    print(info)
    return info


if __name__ == "__main__":
    run()
