"""Consumer de streaming — micro-batch do tópico Kafka para a LANDING (CSV).

Lê o tópico `toll.transactions` e grava um arquivo de MICRO-BATCH (CSV) em
streaming-landing/, no MESMO formato dos arquivos de landing do batch. A partir
daí o caminho é idêntico ao batch: dlt/Auto Loader ingere os micro-batches e o
`fct_toll_transactions` (incremental) processa só o novo.

Uso:  python consumer.py --max 1000 --timeout-ms 8000
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from kafka import KafkaConsumer

BROKER = os.getenv("KAFKA_BROKER", "localhost:19092")
TOPIC = os.getenv("KAFKA_TOPIC", "toll.transactions")
COLUMNS = [
    "transaction_id",
    "vehicle_id",
    "plaza_id",
    "event_ts",
    "amount_cents",
    "payment_method",
    "status",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--max", type=int, default=10_000, help="máx. de mensagens no batch"
    )
    ap.add_argument(
        "--timeout-ms", type=int, default=8000, help="encerra após X ms ocioso"
    )
    ap.add_argument("--out", default="streaming-landing")
    args = ap.parse_args()

    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BROKER,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="toll-sink",
        consumer_timeout_ms=args.timeout_ms,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )

    rows = []
    for msg in consumer:
        rows.append(msg.value)
        if len(rows) >= args.max:
            break
    consumer.close()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = out_dir / f"micro_batch_{stamp}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in COLUMNS})

    print(f"Consumidos {len(rows)} eventos -> micro-batch {path}")
    return len(rows)


if __name__ == "__main__":
    main()
