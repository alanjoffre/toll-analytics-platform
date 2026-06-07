# streaming-toll-analytics — ingestão near-real-time (Kafka/Redpanda)

Demonstra o caminho **streaming → micro-batch → warehouse**, complementar ao batch
(dlt). Passagens de pedágio chegam como eventos num tópico Kafka (**Redpanda**, leve e
Kafka-compatível); um consumidor agrupa em **micro-batches** e grava na landing — daí
em diante o caminho é idêntico ao batch (dlt/Auto Loader → `fct` incremental).

```
producer.py ──▶ Redpanda (tópico toll.transactions) ──▶ consumer.py ──▶ micro-batch CSV
                                                                          (streaming-landing/)
                                                          └─▶ dlt/Auto Loader ─▶ dbt fct (incremental)
```

## Componentes
- [docker-compose.yml](docker-compose.yml) — **Redpanda** (Kafka API em `localhost:19092`) + console (`:8088`).
- [producer.py](producer.py) — emite N eventos JSON (com ~5% de anomalias) ao tópico.
- [consumer.py](consumer.py) — consome em micro-batch e grava CSV no formato da landing.

## Rodar (Docker)
```bash
docker compose up -d --wait redpanda
docker compose exec -T redpanda rpk topic create toll.transactions -p 1
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python producer.py --count 200      # produz
.venv/bin/python consumer.py --max 1000       # consome -> streaming-landing/*.csv
docker compose down
```
Validado (local + CI `streaming_ci.yml`): **200 produzidos → 200 consumidos** num micro-batch.

## Como fecha com o resto
- O micro-batch sai no **mesmo schema** da landing do batch → o `fct_toll_transactions`
  (incremental + lookback, ADR-8) processa só o novo, sem reprocessar histórico.
- **Produção:** trocar o sink CSV por **Auto Loader** (Databricks) ou **Kafka Connect**;
  e o produtor por **CDC (Debezium)** sobre o banco transacional. A camada dbt não muda.

> Honestidade: é um demo de streaming **near-real-time** (micro-batch), não exactly-once
> de baixa latência. Cobre o conceito (broker → consumo → warehouse) de forma validável.
