"""Producer de streaming — emite eventos de passagem de pedágio para o Redpanda/Kafka.

Simula o "tempo real": cada passagem vira uma mensagem JSON no tópico
`toll.transactions`. ~5% com anomalias (igual ao batch), para o consumo/auditoria
encontrarem algo.

Uso:  python producer.py --count 200
"""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import datetime, timezone

from kafka import KafkaProducer

BROKER = os.getenv("KAFKA_BROKER", "localhost:19092")
TOPIC = os.getenv("KAFKA_TOPIC", "toll.transactions")

PLAZAS = ["P001", "P002", "P003", "P004", "P005"]
PAYS = ["AUTOMATIC_TAG", "CASH", "CARD"]
BASE_FARE = {"P001": 1180, "P002": 1450, "P003": 990, "P004": 1620, "P005": 2360}


def _event(i: int) -> dict:
    pid = random.choice(PLAZAS)
    mult = random.choice([1.0, 2.0, 3.0, 4.5])
    amount = round(BASE_FARE[pid] * mult)
    status = "COMPLETED"
    r = random.random()
    if r < 0.02:
        amount += random.choice([-200, 150, 300])  # tarifa divergente
    elif r < 0.03:
        status = random.choice(["FAILED", "REVERSED"])  # cobrança em falha
    elif r < 0.035:
        amount = random.choice([0, None])  # valor inválido
    return {
        "transaction_id": f"S{i:08d}",
        "vehicle_id": f"V{random.randint(0, 999):04d}",
        "plaza_id": pid,
        "event_ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "amount_cents": amount,
        "payment_method": random.choice(PAYS),
        "status": status,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    producer = KafkaProducer(
        bootstrap_servers=BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        acks="all",
    )
    for i in range(1, args.count + 1):
        ev = _event(i)
        producer.send(TOPIC, key=ev["transaction_id"], value=ev)
    producer.flush()
    producer.close()
    print(f"Produzidos {args.count} eventos -> tópico '{TOPIC}' em {BROKER}")


if __name__ == "__main__":
    main()
