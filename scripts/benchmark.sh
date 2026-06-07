#!/usr/bin/env bash
# Benchmark de ESCALA no DuckDB: gera N transações -> dlt ingest -> dbt build,
# medindo o tempo de cada etapa. Não toca no dataset curado (usa scale-data/ + /tmp db).
#   bash scripts/benchmark.sh 100000
set -euo pipefail
SCALE="${1:-100000}"
ING="ingestion-toll-analytics"
DBTDIR="dbt-toll-analytics"
SCALE_DIR="$(pwd)/$ING/scale-data"
SCALE_DB="/tmp/toll_scale.duckdb"

# garante o faker no venv da ingestão
"$ING/.venv/bin/pip" install -q -r "$ING/requirements-dev.txt"

echo "==> gerando $SCALE transações"
"$ING/.venv/bin/python" "$ING/generate_data.py" --scale "$SCALE" --out "$SCALE_DIR"

rm -f "$SCALE_DB"*
echo "==> ingestão (dlt)"; t0=$(date +%s)
TOLL_LANDING_DIR="$SCALE_DIR" DBT_DUCKDB_PATH="$SCALE_DB" "$ING/.venv/bin/python" "$ING/toll_ingestion.py" >/dev/null
t1=$(date +%s)
echo "==> dbt build"
( cd "$DBTDIR" && DBT_DUCKDB_PATH="$SCALE_DB" .venv/bin/dbt build --exclude tag:observability --no-partial-parse --profiles-dir . 2>&1 | grep -E "Done\. PASS=|ERROR=[1-9]" | tail -1 )
t2=$(date +%s)

echo ""
echo "=== BENCHMARK (DuckDB, escala=$SCALE) ==="
echo "ingestão (dlt):  $((t1-t0))s"
echo "dbt build:       $((t2-t1))s"
echo "total:           $((t2-t0))s"
"$ING/.venv/bin/python" - "$SCALE_DB" <<'PY'
import duckdb, sys
c = duckdb.connect(sys.argv[1], read_only=True)
print("fct linhas:     ", c.sql("select count(*) from main.fct_toll_transactions").fetchone()[0])
print("suspeitas:      ", c.sql("select count(*) from main.audit_suspect_transactions").fetchone()[0])
print(c.sql("select audit_flag, count(*) n from main.audit_suspect_transactions group by 1 order by 2 desc"))
PY
