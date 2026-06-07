"""Gerador de dados sintéticos em ESCALA (faker) — para benchmark/teste de carga.

Produz um dataset realista e MAIOR (N transações) que respeita as invariantes que
o dbt testa (FKs válidas, vigências de tarifa NÃO sobrepostas, enums válidos) e
INJETA anomalias (~5%) para a auditoria encontrar. Escreve os mesmos 5 CSVs de
landing num diretório separado (default: scale-data/), para NÃO tocar no dataset
curado pequeno (que os testes determinísticos usam).

Uso:
    python generate_data.py --scale 100000 --out scale-data --seed 42

Depois (benchmark):
    TOLL_LANDING_DIR=scale-data DBT_DUCKDB_PATH=/tmp/toll_scale.duckdb python toll_ingestion.py
    cd ../dbt-toll-analytics && DBT_DUCKDB_PATH=/tmp/toll_scale.duckdb dbt build ...
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

PLAZAS = [
    ("P001", "Praça Norte", "BR-101", "SP"),
    ("P002", "Praça Sul", "BR-116", "RJ"),
    ("P003", "Praça Leste", "BR-040", "MG"),
    ("P004", "Praça Oeste", "BR-153", "PR"),
    ("P005", "Praça Central", "BR-376", "SC"),
]
CATEGORIES = [(2, "Automovel", 1.0), (4, "Caminhao 2 eixos", 2.0),
              (6, "Caminhao 3 eixos", 3.0), (9, "Carreta", 4.5)]
# tarifa base por praça (centavos); duas vigências não-sobrepostas (SCD2)
BASE_FARE = {"P001": 1180, "P002": 1450, "P003": 990, "P004": 1620, "P005": 2360}
WINDOW_START = datetime(2026, 1, 1)
WINDOW_MID = datetime(2026, 4, 1)
WINDOW_END = datetime(2026, 6, 30)


def _fare_for(plaza_id: str, event_dt: datetime) -> int:
    """Tarifa vigente na data (point-in-time): +5% a partir de WINDOW_MID."""
    base = BASE_FARE[plaza_id]
    return base if event_dt < WINDOW_MID else round(base * 1.05)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=100_000, help="nº de transações")
    ap.add_argument("--out", default="scale-data")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    fake = Faker("pt_BR")
    Faker.seed(args.seed)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # --- dimensões ---
    with open(out / "raw_toll_plazas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["plaza_id", "plaza_name", "highway", "uf"])
        w.writerows(PLAZAS)

    with open(out / "raw_vehicle_categories.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["category", "description", "fare_multiplier"])
        w.writerows(CATEGORIES)

    # tarifa: 2 vigências NÃO sobrepostas por praça (mutually_exclusive_ranges)
    with open(out / "raw_fare_schedule.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["plaza_id", "fare_cents", "valid_from", "valid_to"])
        for pid, base in BASE_FARE.items():
            w.writerow([pid, base, "2026-01-01", "2026-03-31"])
            w.writerow([pid, round(base * 1.05), "2026-04-01", "2026-12-31"])

    # veículos (escala com o volume; mínimo 50)
    n_vehicles = max(50, args.scale // 20)
    vehicles = []
    with open(out / "raw_vehicles.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["vehicle_id", "plate", "category", "account_id"])
        for i in range(n_vehicles):
            vid = f"V{i:06d}"
            cat = random.choice(CATEGORIES)[0]
            plate = f"{fake.lexify('???').upper()}{fake.numerify('#')}{fake.lexify('?').upper()}{fake.numerify('##')}"
            acc = f"ACC{random.randint(1, n_vehicles // 5 + 1):05d}"
            vehicles.append((vid, cat))
            w.writerow([vid, plate, cat, acc])

    cat_mult = {c[0]: c[2] for c in CATEGORIES}
    statuses = ["COMPLETED", "FAILED", "REVERSED"]
    pays = ["AUTOMATIC_TAG", "CASH", "CARD"]
    span = int((WINDOW_END - WINDOW_START).total_seconds())

    # --- transações (com ~5% de anomalias injetadas) ---
    with open(out / "raw_toll_transactions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["transaction_id", "vehicle_id", "plaza_id", "event_ts",
                    "amount_cents", "payment_method", "status"])
        tid = 0
        for _ in range(args.scale):
            tid += 1
            vid, cat = random.choice(vehicles)
            pid = random.choice(PLAZAS)[0]
            ev = WINDOW_START + timedelta(seconds=random.randint(0, span))
            expected = round(_fare_for(pid, ev) * cat_mult[cat])
            amount, status = expected, "COMPLETED"
            r = random.random()
            if r < 0.02:          # tarifa divergente
                amount = expected + random.choice([-200, -100, 150, 300])
            elif r < 0.03:        # cobrança em falha (valor > 0)
                status = random.choice(["FAILED", "REVERSED"])
            elif r < 0.035:       # valor inválido (zero/nulo)
                amount = random.choice([0, None])
            w.writerow([f"T{tid:08d}", vid, pid, ev.strftime("%Y-%m-%d %H:%M:%S"),
                        "" if amount is None else amount,
                        random.choice(pays), status])
            # ~0.5%: duplicidade na janela (mesma passagem em < 5 min)
            if r > 0.995:
                tid += 1
                ev2 = ev + timedelta(seconds=random.randint(10, 280))
                w.writerow([f"T{tid:08d}", vid, pid, ev2.strftime("%Y-%m-%d %H:%M:%S"),
                            expected, random.choice(pays), "COMPLETED"])

    print(f"Gerado em {out}/: {args.scale} transações (~{tid} linhas), "
          f"{n_vehicles} veículos, {len(PLAZAS)} praças.")


if __name__ == "__main__":
    main()
