# ingestion-toll-analytics

Camada de **ingestão (EL)** com **[dlt](https://dlthub.com)** — o "E" e o "L" do
ELT, antes do "T" (dbt). Lê os arquivos de **landing** (`data/*.csv`, tratados como
arquivos que "caem" de um sistema upstream) e carrega no schema **`landing`** do
DuckDB. O dbt então consome via `source('toll_raw', ...)`.

```
data/*.csv  ──[dlt]──▶  DuckDB schema `landing`  ──[dbt source()]──▶  staging → ... → marts
```

## O que demonstra
- **EL real** (não só seeds): extract de arquivos + load no warehouse.
- **Disposições de escrita**: `merge` (idempotente por `primary_key`, dedup) para
  transações/entidades; `replace` (full reload) para a dim de tarifa.
- **Metadados de carga** do dlt (`_dlt_load_id`, `_dlt_loads`) — rastreabilidade.
- **Normalização de EL**: campo vazio do CSV (`''`) vira **NULL** (ausente).
- **Reprodutível offline**: lê CSVs commitados, não uma API externa.

## Rodar
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python toll_ingestion.py          # -> schema landing no DuckDB do dbt
```
Por padrão grava no DuckDB do projeto dbt (`../dbt-toll-analytics/toll_analytics.duckdb`);
sobrescreva com `DBT_DUCKDB_PATH` (a orquestração aponta para um arquivo em `/tmp`).

## Escala / benchmark (Fase 9)
`generate_data.py` (faker) cria um dataset **grande e realista** que respeita as
invariantes testadas pelo dbt (FKs válidas, vigências de tarifa não-sobrepostas, enums)
e **injeta ~5% de anomalias** — usado só para benchmark, num diretório/DuckDB separados
(NÃO toca no dataset curado dos testes determinísticos).

```bash
bash ../scripts/benchmark.sh 100000   # gera -> dlt -> dbt build, medindo o tempo
```

Resultado medido (DuckDB local, **100.000 transações**):

| Etapa | Tempo |
|---|---|
| Ingestão (dlt) | ~9 s |
| dbt build (run + testes) | ~14 s |
| **Total** | **~23 s** · `PASS=192 ERROR=0` |

O fato fica com **100.472 linhas** e a auditoria encontra **6.988 suspeitas**
(4578 tarifa divergente, 1012 cobrança em falha, 935 duplicidade, 463 valor inválido)
— a lógica de auditoria escala junto.

> **Escala real (Databricks):** para volumes muito maiores, o `fct` usaria a estratégia
> incremental **microbatch** (por `event_time`) e **particionamento/liquid clustering** —
> features do warehouse, não do DuckDB single-node (ADR-24). No dev, o DuckDB já entrega
> centenas de milhares de linhas em segundos.

## Onde encaixa
- **Orquestração:** o DAG `toll_analytics_pipeline` roda `ingest_landing` (este dlt)
  **antes** do transform (Cosmos). Ver `../airflow-toll-analytics`.
- **CI:** os workflows de dbt rodam `dlt → dbt build`.
- **Decisão:** ADR-28 (e ADR-13) em `../dbt-toll-analytics`.

> Em produção, os CSVs dariam lugar a conectores reais do dlt (APIs/DB/SaaS) ou a
> ingestão nativa do warehouse (Auto Loader / COPY INTO no Databricks). Os modelos
> dbt a jusante não mudam — só a fonte.
