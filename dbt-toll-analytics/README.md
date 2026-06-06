# dbt-toll-analytics

Produto de dados de **analytics + auditoria de vale-pedágio** construído com **dbt**,
rodando localmente em **DuckDB** (sem nuvem, sem custo) e **portável para Databricks**
trocando só o `profiles.yml`. Tudo com **dados sintéticos** — nenhum dado real de cliente.

Ingere transações de pedágio cruas, modela em camadas **Medallion** (bronze → silver →
gold) e entrega (a) marts dimensionais confiáveis e (b) um modelo de **auditoria** que
sinaliza transações suspeitas (tarifa divergente, cobrança em falha, valor inválido,
possível duplicidade).

> O domínio (mobilidade/pagamentos) foi escolhido por ficar perto de engenharia de
> dados real, sem expor nada confidencial. O cérebro do projeto (o porquê de cada
> técnica) está em [PLANO_DO_PROJETO.md](PLANO_DO_PROJETO.md).

---

## O que este projeto demonstra (portfólio / entrevista)

| Técnica | Onde está |
|---|---|
| **Ingestão (EL) com dlt** → schema `landing` | [`../ingestion-toll-analytics`](../ingestion-toll-analytics) (ADR-28) |
| **Medallion** (bronze/silver/gold) em dbt | `landing` (dlt) · `models/staging/` · `models/intermediate/` + `models/marts/` |
| **Tarifa point-in-time** (SCD2 via schedule) | `stg_fare_schedule` + join temporal em `int_transactions_enriched` |
| **Snapshot** (SCD2 nativo do dbt) | `snapshots/snap_toll_plazas.sql` |
| **Model incremental** (`unique_key` + `is_incremental` + **lookback** anti late-arriving) | `models/marts/fct_toll_transactions.sql` |
| **Semantic Layer** (MetricFlow: métricas governadas) | `models/marts/_semantic_models.yml` |
| **Guarda contra fan-out** (`mutually_exclusive_ranges`) | `stg_fare_schedule` em `_staging.yml` |
| **Ambientes dev/prod** | `profiles.yml` (`--target prod`) |
| **Sources + source freshness** (contrato de ingestão) | `models/staging/_sources.yml` |
| **Dinheiro em centavos inteiros** (sem erro de float) | `agg_daily_revenue_by_plaza.sql`, medidas do Semantic Layer |
| **CI endurecido** (lint models+tests+snapshots+macros, cache, docs) | `.github/workflows/dbt_ci.yml` |
| **Surrogate keys** | `dbt_utils.generate_surrogate_key` nas dims e no fato |
| **Model contracts** (trava colunas + tipos) | `models/marts/_marts.yml` (`contract: enforced`) |
| **Unit tests** (dbt 1.8+, lógica mockada) | `models/marts/_unit_tests.yml` |
| **Teste genérico customizado** + **singular** | `tests/generic/` · `tests/` |
| **dbt_utils** + **dbt_expectations** | `accepted_range` etc. |
| **Observabilidade** (`store_failures` + `on-run-end`) | `macros/log_run_results.sql` → tabela `_audit_runs` |
| **Detecção de anomalia (Elementary)** — job agendado (`tag:observability`) | `_marts.yml` + `.github/workflows/observability.yml` |
| **Testes no formato `arguments:`** (zero deprecation) | todos os `_*.yml` |
| **Severidade** (`warn` × `error`) com racional | `not_charged_when_failed` (warn) em `_marts.yml` |
| **Exposure** (consumidor no lineage) | `models/exposures.yml` |
| **Masking de PII** (LGPD) | `stg_vehicles` (placa mascarada) |
| **CI** (dbt build + SQLFluff) | `.github/workflows/dbt_ci.yml` |
| **Groups + access** (governança de modelos) | `models/_groups.yml` + `dbt_project.yml` |
| **Constraints no warehouse** (PK/CHECK via contract) | `models/marts/_marts.yml` |
| **Model ephemeral** (CTE inlinada) | `models/intermediate/int_duplicate_flags.sql` |
| **Python model** (pandas: z-score por praça) | `models/marts/py_plaza_audit_stats.py` |
| **Versioned model** (v1→v2 + `deprecation_date`) | `models/marts/rpt_plaza_revenue_v*.sql` |
| **dbt_project_evaluator** (auditoria de best practices) | `packages.yml` (`severity: warn`) |

---

## Arquitetura (Medallion)

```
   BRONZE (seeds)            SILVER (staging)              GOLD (intermediate + marts)
 raw_toll_plazas    ─►  stg_toll_plazas         ─┐
 raw_fare_schedule  ─►  stg_fare_schedule       ─┤                    dim_plaza
 raw_vehicles       ─►  stg_vehicles            ─┼─► int_transactions ─► dim_vehicle / dim_date
 raw_vehicle_cat.   ─►  stg_vehicle_categories  ─┤    _enriched        fct_toll_transactions
 raw_toll_trans.    ─►  stg_toll_transactions   ─┘  (point-in-time +   agg_daily_revenue_by_plaza
                          (dedup, PII, tipos)        duplicidade)      audit_suspect_transactions ◄─ PRODUTO
```

- **Bronze:** CSV cru, com imperfeições propositais (duplicata, valor nulo/zero, tarifa divergente, cobrança em falha).
- **Silver:** 1 model por fonte — tipagem, limpeza, **dedup**, **masking de PII**. Sem join entre fontes.
- **Gold:** intermediate enriquece (joins + regra de negócio); marts entregam o modelo dimensional, agregações e a auditoria.

---

## Como rodar (local, ~3 min)

```bash
cd dbt-toll-analytics
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

dbt deps  --profiles-dir .

# INGESTÃO (EL) primeiro: o bronze vem do dlt (schema landing), não de seeds (ADR-28).
( cd ../ingestion-toll-analytics && python3 -m venv .venv \
  && .venv/bin/pip install -r requirements.txt && .venv/bin/python toll_ingestion.py )

dbt build --profiles-dir .                 # transforma a partir do source (dev/DuckDB)
# (atalho: `make build` já roda a ingestão antes do build)
# prod = Databricks REAL (Unity Catalog + Delta): requer credenciais e
# `pip install -r requirements-databricks.txt`. Ver "Portar para Databricks".

# documentação + lineage no navegador
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .
```

Inspecionar o produto de auditoria:
```bash
python -c "import duckdb; c=duckdb.connect('toll_analytics.duckdb'); \
print(c.sql('select audit_flag, count(*) from main.audit_suspect_transactions group by 1 order by 2 desc'))"
```

Saída esperada (9 transações suspeitas):

| audit_flag | n |
|---|---|
| TARIFA_DIVERGENTE | 3 |
| VALOR_INVALIDO | 2 |
| POSSIVEL_DUPLICIDADE | 2 |
| COBRANCA_EM_FALHA | 2 |

> O `dbt build` termina com **1 WARN intencional** (`not_charged_when_failed`): há
> cobranças em transações FAILED/REVERSED de propósito nos seeds — a auditoria as
> sinaliza, então é alerta monitorável (severidade `warn`), não falha de build.

---

## Rotinas (Makefile) e documentação sempre em dia

Atalhos para as tarefas comuns (precisa do `.venv` criado acima):
```bash
make build         # dbt build (CI de PR) + REGENERA a doc Word + checa drift
make docs          # regenera só o documento Word
make check-docs    # verifica se a doc está em dia com o código (falha se não)
make lint          # SQLFluff (models, tests, snapshots, macros)
make observability # testes de anomalia (tag:observability)
make freshness     # dbt source freshness
```

**Anti-drift:** a documentação Word é gerada por `docs/gerar_documentacao.py` (conteúdo
versionado). Como o conteúdo é escrito à mão, `docs/check_docs_sync.py` compara o Word com
o **código real** e **falha se algum ADR ou arquivo do projeto não estiver coberto**. Esse
check roda no `make build` e no **CI de cada PR** — então a documentação nunca fica atrás
do código sem alguém ser avisado.

## Orquestração (Airflow + Cosmos) — projeto irmão

Este projeto entrega a **camada de transformação**. A **orquestração** vive ao lado,
em [`../airflow-toll-analytics`](../airflow-toll-analytics), usando **Astronomer Cosmos**:
cada model/seed/snapshot/test do dbt vira **uma task** do Airflow (lineage real), com
agendamento, retries, gate de `source freshness`, alertas e um DAG separado de
observabilidade.

```
source_freshness ──▶ [ transform: 1 task por nó do dbt (Cosmos) ] ──▶ generate_docs
```

Validação ponta-a-ponta (sobe Airflow num venv e roda o pipeline num DuckDB limpo):
```bash
cd ../airflow-toll-analytics && bash scripts/validate_local.sh
```

Decisões dessa camada (no README do projeto irmão): **ADR-A1** dbt fora do ambiente do
Airflow (sem conflito de deps); **ADR-A2** DuckDB é single-writer → pool de 1 slot +
DuckDB local em `/tmp` para serializar e evitar lock; **ADR-A3** observabilidade
(anomalia Elementary) isolada num DAG agendado, fora do caminho crítico.

> Nota de portabilidade: o lock que o Airflow contorna é **artefato do DuckDB**
> (single-writer); em Databricks/Snowflake a concorrência é nativa e o pool sai.

---

## A técnica-estrela: tarifa point-in-time

O preço do pedágio muda no tempo. Comparar uma transação **antiga** com a tarifa
**atual** gera **falso positivo** de "tarifa divergente". A solução é juntar a
transação à `fare_schedule` pela **data do evento** (`event_date BETWEEN valid_from
AND valid_to`) — a tarifa vigente *naquele dia*.

Exemplo real nos dados (praça P003, carreta cat 9 ×4.5; tarifa muda 990→1050 em 2026-05-03):

| Transação | Data | Valor | Esperado (point-in-time) | Resultado |
|---|---|---|---|---|
| T0006 | 01/05 | 4455 | 990 × 4.5 = **4455** | **OK** (não acusa) |
| T0023 | 03/05 | 4455 | 1050 × 4.5 = **4725** | **TARIFA_DIVERGENTE** |

Com a tarifa atual ingênua (1050), T0006 seria marcada errada como divergente. É o que
separa o modelo júnior (join na tarifa atual) do sênior (join point-in-time).

---

## ADRs — Architecture Decision Records

Decisões registradas porque **julgamento documentado** é o que mais sinaliza senioridade.

### ADR-1 — Tarifa em `fare_schedule` (seed), não em `toll_plazas`
**Decisão:** a tarifa não é atributo da praça; vive numa tabela própria com vigência
(`valid_from`/`valid_to`). **Por quê:** preço tem história; modelar como SCD2 permite o
join point-in-time e evita falso positivo. **Trade-off:** um join a mais, em troca de
correção temporal — sempre vale.

### ADR-2 — Histórico de tarifa via seed, e não via snapshot
**Decisão:** o histórico determinístico de tarifa usa a seed `raw_fare_schedule`; o
`snapshot` fica como demonstração da técnica em `snap_toll_plazas`. **Por quê:** snapshot
constrói história **ao longo de várias execuções** (CDC) — na 1ª execução não há histórico.
Para um portfólio reprodutível, preciso da história **já na 1ª `dbt build`**. **Trade-off:**
dois mecanismos de SCD2 no projeto, mas cada um demonstrando o caso de uso certo.

### ADR-3 — Valores inválidos: flag, não delete
**Decisão:** valor nulo/zero **não** é removido nem quebra teste — é mantido e sinalizado
pela auditoria. **Por quê:** em auditoria a regra é *flag, não delete* (rastreabilidade).
Por isso `not_null` fica só nas chaves; o valor é regra de negócio no produto.

### ADR-4 — Fato `incremental` com `unique_key`
**Decisão:** `fct_toll_transactions` é incremental, filtrando por `event_date >
max(event_date)`. **Por quê:** em escala não reprocessa o histórico; `unique_key` garante
idempotência. **Trade-off:** lógica `is_incremental()` a mais; em troca, custo de execução
que não cresce com o histórico.

### ADR-5 — Regra de auditoria isolada na macro `audit_flag`
**Decisão:** a classificação (com prioridade entre anomalias) vive numa macro, coberta por
**unit tests**. **Por quê:** regra de negócio testável e reutilizável, desacoplada dos
dados reais. **Trade-off:** indireção Jinja, em troca de testes determinísticos da lógica.

### ADR-6 — Severidade `warn` para `not_charged_when_failed`
**Decisão:** cobranças em FAILED/REVERSED disparam `warn`, não `error`. **Por quê:** são
exatamente o que a auditoria existe para encontrar; quebrar o build seria contraditório.
`error` fica para invariantes que *nunca* podem ocorrer (unicidade de PK, contratos).

### ADR-7 — DuckDB local, portável para Databricks
**Decisão:** desenvolver em DuckDB; produção em Databricks trocando o adapter. **Por quê:**
loop de feedback local instantâneo e sem custo; os **models SQL são os mesmos**. **Trade-off:**
funções específicas de dialeto exigiriam atenção — mantidas no mínimo de propósito.

### ADR-8 — Incremental com janela de lookback (late-arriving data)
**Decisão:** o filtro incremental usa `event_date >= max(event_date) - N dias`
(`var('incremental_lookback_days')`, default 3), e não `> max(event_date)`. **Por quê:**
um filtro estrito `> max` descartaria **para sempre** uma transação que chega atrasada
(data menor que o máximo já carregado) — o bug clássico de incremental. A janela de
lookback reprocessa os últimos N dias; o `unique_key` (merge) deduplica, então não há
risco de duplicar. **Trade-off honesto:** transações que chegam com atraso **maior** que
N dias ainda escapam — N é o ajuste entre custo de reprocessamento e tolerância a atraso.

### ADR-9 — Guarda declarativa contra fan-out no join point-in-time
**Decisão:** `stg_fare_schedule` tem o teste `dbt_utils.mutually_exclusive_ranges`
(por `plaza_id`). **Por quê:** o join temporal (`event_date BETWEEN valid_from AND
valid_to`) casaria **duas** linhas se as vigências de uma praça se sobrepusessem,
**duplicando a transação silenciosamente** — e o incremental mascararia isso. O teste
trava a invariante que sustenta a chave do produto inteiro. **Trade-off:** nenhum
relevante; é uma asserção barata que previne um bug caro.

### ADR-10 — `dim_date` com faixa derivada dos dados
**Decisão:** o `date_spine` usa anos-calendário derivados do min/max real das transações,
não um intervalo fixo de 2026. **Por quê:** uma faixa fixa quebraria o teste de
`relationships` em `date_key` assim que chegasse uma transação fora do ano. **Trade-off:**
uma introspective query (`run_query`) no compile do modelo, em troca de robustez.

### ADR-11 — Semantic Layer (MetricFlow) em vez de só agregações fixas
**Decisão:** as métricas de negócio (`revenue`, `suspect_rate`, `revenue_leakage_brl`…)
são definidas no Semantic Layer, sobre o fato, e não como tabelas `agg_*` por recorte.
**Por quê:** uma definição central, consultável por qualquer dimensão, evita a
proliferação de agregações e garante **consistência de métrica** (a "receita" é a mesma
em todo lugar). A `agg_daily_revenue_by_plaza` foi mantida como exemplo de agregação
materializada clássica. **Trade-off:** consultar métricas exige o runtime MetricFlow
(`mf query` / dbt Cloud), mas a definição é versionada e testável no `dbt parse`.

### ADR-12 — `audit_flag` materializada no fato
**Decisão:** o fato carrega a coluna `audit_flag` (mesma macro do produto de auditoria).
**Por quê:** habilita as métricas de suspeita no Semantic Layer sem duplicar regra (a
lógica vive na macro `audit_flag` — DRY). **Trade-off:** uma coluna a mais no fato, em
troca de análise de qualidade direto no grão transacional.

### ADR-14 — Observabilidade de dados com Elementary
**Decisão:** integrei o pacote `elementary-data/elementary` (schema `elementary`) e um
teste de **detecção de anomalia** (`elementary.volume_anomalies`) no fato. As tabelas de
monitoramento (`elementary_test_results`, `dbt_run_results`, `data_monitoring_metrics`…)
são materializadas **no próprio warehouse** a cada execução. **Por quê:** é o salto de
"tenho metadados" (`_audit_runs`) para "monitoro dados" (anomalias + histórico de testes).
**Trade-offs honestos (DuckDB):** (1) anomaly detection precisa de **histórico de várias
execuções** para treinar baseline — com um snapshot único o teste roda mas tende a
reportar dados insuficientes, por isso fica em `warn`; (2) o **relatório HTML** do CLI
`edr` tem suporte ainda **áspero no DuckDB** (a camada in-warehouse funciona; o report
interativo é melhor suportado em Snowflake/BigQuery/Databricks); (3) o adapter emite
mensagens cosméticas "Tried to commit transaction" — ruído, não erro.

### ADR-13 — `sources` + `freshness` sobre os seeds (contrato de ingestão)
**Decisão:** declarei `sources` (`toll_raw`) apontando para as tabelas que os seeds
materializam, com `freshness` na tabela de transações; o staging continua usando `ref()`
nos seeds. **Por quê:** quero o **contrato de ingestão** (SLA de atraso) explícito, sem
perder o bronze reprodutível offline. Trocar `ref()`→`source()` quebraria a ordem do DAG
(o seed não é dependência de um `source()`). **Trade-off honesto:** o lineage não liga
source→staging em dev; em prod, os seeds viram tabelas de ingestão e o staging passa a
usar `source()` — aí o lineage fica completo. Contra o snapshot sintético (maio/2026), o
`dbt source freshness` reporta **WARN** (dataset estático) — esperado; com ingestão real
fica verde.

### ADR-15 — Dinheiro agregado em centavos inteiros (não em float)
**Decisão:** agregações monetárias somam `amount_cents` (inteiro, exato) e convertem para
BRL **só no final** (`cents_to_brl(sum(...))`); nunca somam `amount_brl` (reais já
arredondados). Vale para `agg_daily_revenue_by_plaza` e para as medidas do Semantic Layer
(`revenue_cents`/`leakage_cents` → métricas derivadas `/100`). **Por quê:** somar valores
já arredondados acumula erro de arredondamento/float — anti-padrão clássico em dado
financeiro. Centavos inteiros são exatos; a conversão acontece uma única vez, na exibição.
**Trade-off:** nenhum — os números batem (215,65/183,95/145,65) e a corretude é garantida.

### ADR-16 — Testes genéricos no formato `arguments:`
**Decisão:** todos os testes genéricos (`relationships`, `accepted_values`,
`accepted_range`, `mutually_exclusive_ranges`, customizados) passaram a aninhar os
parâmetros sob a chave `arguments:`. **Por quê:** o dbt 1.11+ deprecou passar argumentos
de teste no nível de cima (`MissingArgumentsPropertyInGenericTestDeprecation`); o novo
formato remove os warnings e é à prova do dbt 2.0. **Validação:** `dbt parse` agora roda
sem nenhum aviso de deprecation. **Trade-off:** uma linha de indentação a mais por teste,
em troca de zero dívida de deprecation.

### ADR-17 — Observabilidade (Elementary) como job agendado, fora do build de PR
**Decisão:** o teste de anomalia (`elementary.volume_anomalies`) recebeu a tag
`observability`; o CI de PR roda `dbt build --exclude tag:observability`, e um workflow
**agendado** (`observability.yml`) roda `dbt test --select tag:observability`. No build de
PR, o autoupload do Elementary fica desligado (`vars: elementary: disable_*`). **Por quê:**
(1) detecção de anomalia só é significativa com **histórico acumulado** de várias execuções
— no PR (snapshot único) reportaria sempre "dados insuficientes"; (2) no adapter
`dbt-duckdb`, a captura automática em `on-run-end` dispara um erro de commit de transação.
Separar em um job agendado dá ao baseline o histórico de que ele precisa e mantém o PR
limpo e determinístico (`PASS=124`). **Trade-off:** a observabilidade não roda a cada PR —
correto, porque ela é monitoramento contínuo, não um gate de merge.

### ADR-18 — Groups + access (governança de modelos)
**Decisão:** cada model pertence a um `group` (`staging`/`intermediate`/`marts`) com dono;
o interno é `access: protected` (só o package referencia) e os marts são `public` (camada
consumível por BI/Semantic Layer/exposures). **Por quê:** torna explícitas as fronteiras de
consumo. **Trade-off:** `private` não se aplica aqui — nossos `ref()` cruzam grupos, e
private restringe ao mesmo grupo.

### ADR-19 — Constraints no warehouse (PK/CHECK via contract)
**Decisão:** com `contract: enforced`, declaramos `primary_key`/`not_null`/`check` que viram
**DDL real** na CREATE TABLE — o banco garante a invariante, não só o teste dbt. PK no grão
do fato e das dims; CHECK em `dim_date` (mês 1..12, dia da semana 0..6). **Trade-off:**
constraints exigem contract; em troca, a integridade é garantida pelo motor.

### ADR-20 — Model ephemeral (`int_duplicate_flags`)
**Decisão:** a detecção de duplicidade virou um model **ephemeral** (inlinado como CTE, sem
objeto no banco), consumido pelo `int_transactions_enriched`. **Por quê:** separa "achar
duplicata" de "enriquecer"; uso clássico de ephemeral (passo lógico barato e reutilizável).

### ADR-21 — Python model (`py_plaza_audit_stats`)
**Decisão:** um model em **Python** (dbt-duckdb) calcula a taxa de suspeita e o **z-score
entre praças** em pandas. **Por quê:** o dbt orquestra/testa/versiona Python igual a SQL;
estatística é natural em pandas. Usado onde agrega valor, não por moda.

### ADR-22 — Versioned model + `deprecation_date`
**Decisão:** `rpt_plaza_revenue` é **versionado** — v2 (latest) adiciona ticket médio; v1
fica deprecada até 2026-12-31. **Por quê:** quebra de contrato via **versão**, não in-place:
consumidores migram no seu ritmo. `ref('rpt_plaza_revenue')` resolve para a `latest_version`.

### ADR-23 — `dbt_project_evaluator` como `warn`
**Decisão:** o pacote audita o **próprio projeto** contra best practices (naming, fanout,
undocumented, public sem contract...); as descobertas ficam em `warn`. **Por quê:** melhoria
contínua monitorável, não gate de merge.

### ADR-24 — Materializações/grants só no target prod (Databricks)
**Decisão:** `materialized_view`, estratégia incremental **microbatch** e **grants** são
configurados no target **prod** (Databricks/Delta), não no DuckDB single-node de dev. **Por
quê:** são features de warehouse; em vez de falsear no dev, ficam para prod. No DuckDB rodam
as materializações suportadas (`view`/`table`/`incremental`/`ephemeral`).

### ADR-25 — Docs blocks + persist_docs
**Decisão:** descrições reutilizáveis viram **docs blocks** (`{% docs %}` em `models/docs.md`,
referenciados com `doc()`), e `+persist_docs` empurra as descrições para **COMMENTs no banco**.
**Por quê:** documentação versionada, sem duplicação, e que vive **junto do dado**. **Validado:**
o COMMENT do `audit_flag` no DuckDB traz o docs block renderizado.

### ADR-26 — Saved queries + exports (Semantic Layer)
**Decisão:** uma **saved query** (`revenue_daily`) agrupa métricas + recorte + export, no
Semantic Layer. **Por quê:** consulta governada e reaproveitável (em vez de cada dashboard
copiar SQL); o export materializa a métrica numa tabela. **Trade-off:** o export roda no dbt
Cloud / `mf export`; em core a definição é versionada e validada (`mf validate-configs`).

### ADR-27 — Slim CI (state:modified+ --defer)
**Decisão:** um workflow de PR (`dbt_slim_ci.yml`) constrói **só o que mudou + downstream**,
deferindo o resto a um baseline (manifest da branch base). **Por quê:** reconstruir tudo a
cada PR é caro; o Slim CI roda em segundos quando pouca coisa muda. **Validado:**
`dbt ls --select state:modified+ --state <base>` seleciona exatamente o model alterado (e
nada, quando não há mudança). Em prod, o `--defer` aponta para o warehouse.

### ADR-28 — Ingestão (EL) com dlt; bronze deixa de ser seed
**Decisão:** o bronze não é mais seed. Um pipeline **dlt** ([`../ingestion-toll-analytics`](../ingestion-toll-analytics))
lê os arquivos de landing (CSV) e carrega no schema `landing` do DuckDB (merge/replace,
metadados de carga, `'' → NULL`); o staging passa a consumir via `source('toll_raw', ...)`.
**Por quê:** realiza o ADR-13 — pipeline EL→T de verdade (extract+load + transform), não só
transformação. **Continua reprodutível offline** (o dlt lê CSVs commitados, não uma API). O
Airflow roda a ingestão antes do transform; o CI também (`dlt → dbt build`). **Aprendizado
honesto:** o raw sujo (`''`, timestamps) exige cuidado de tipagem — normalizamos `'' → NULL`
no EL e tipamos no staging (silver).

---

## Limitações conhecidas e roadmap (o que eu faria a seguir)

> Recrutador técnico não busca o projeto "perfeito" — busca quem **reconhece o próprio
> risco antes de ser perguntado**. Esta seção é proposital.

- **Late-arriving além da janela:** o lookback (ADR-8) cobre N dias; atrasos maiores
  exigiriam uma estratégia de reprocessamento por partição. Mitigado e documentado.
Roadmap concluído:
(✅ *sources + freshness — ADR-13; Elementary/observabilidade — ADR-14;*
*orquestração Airflow + Cosmos — em [`../airflow-toll-analytics`](../airflow-toll-analytics), validada ponta-a-ponta;*
*docs hospedados — workflow `.github/workflows/dbt_docs.yml` publica o `dbt docs` no GitHub Pages.*)

> **GitHub Pages (1x manual):** Settings → Pages → Source: **GitHub Actions**. Depois,
> cada push na `main` republica o lineage navegável (`dbt docs generate --static`).

### Contrato de ingestão (source freshness)
```bash
dbt source freshness --profiles-dir .
# Contra o seed estático reporta WARN (esperado); com ingestão real fica verde.
```

### Observabilidade de dados (Elementary)
Os modelos do Elementary são construídos junto com o `dbt build` (schema `elementary`).
A **detecção de anomalia** roda separada (job agendado, ADR-17) — não no build de PR:
```bash
dbt test --select tag:observability --profiles-dir .   # job agendado de observabilidade
```
A camada in-warehouse funciona no DuckDB; inspecione direto:
```bash
python -c "import duckdb; c=duckdb.connect('toll_analytics.duckdb'); \
print(c.sql('select status, count(*) from main_elementary.elementary_test_results group by 1'))"
```
O relatório HTML interativo (`edr report`) é melhor suportado em warehouses cloud
(Snowflake/BigQuery/Databricks) — ver ADR-14.

---

## Consultar métricas (Semantic Layer)

Após `pip install dbt-metricflow` (já no `requirements.txt`):
```bash
export DBT_PROFILES_DIR=.
mf query --metrics revenue,suspect_rate --group-by metric_time__day
mf query --metrics revenue_leakage_brl  --group-by toll_transactions__plaza_id
```
Exemplo de saída real:
```
metric_time__day       revenue    suspect_rate
-------------------  ---------  --------------
2026-05-01              215.65        0.272727
2026-05-02              183.95        0.333333
2026-05-03              145.65        0.500000
```

---

## Portar para Databricks (já configurado)

O target **`prod` do [`profiles.yml`](profiles.yml) já é Databricks** (Unity Catalog +
Delta) — não é hipótese. Para rodar em produção:
```bash
pip install -r requirements-databricks.txt
export DBX_HOST=... DBX_HTTP_PATH=... DBX_TOKEN=... DBX_CATALOG=... DBX_SCHEMA=...
dbt build --profiles-dir . --target prod
```
Os env_var têm default, então o `dev` (DuckDB) continua rodando offline sem nenhuma
dessas variáveis. Equivalências: `table`/`incremental` → **Delta** (incremental usa
`MERGE`); índices → **liquid clustering**/`ZORDER`; seeds → na prática viriam de ingestão
(Auto Loader/COPY INTO). **Os models SQL não mudam** — só o bloco de conexão.

---

## Estrutura

```
dbt-toll-analytics/
├── dbt_project.yml              # vars, on-run-end, store_failures, contracts
├── profiles.yml                 # conexão DuckDB (trocável p/ Databricks)
├── packages.yml                 # dbt_utils, dbt_expectations
├── seeds/                       # BRONZE — CSV cru + _seeds.yml
├── models/
│   ├── staging/                 # SILVER — stg_* + _staging.yml + _sources.yml (freshness)
│   ├── intermediate/            # int_transactions_enriched (point-in-time)
│   ├── marts/                   # GOLD — dims, fato, agg, auditoria, contracts, unit tests
│   │   └── _semantic_models.yml # Semantic Layer (MetricFlow): métricas governadas
│   └── exposures.yml            # consumidor downstream no lineage
├── snapshots/snap_toll_plazas.sql
├── macros/                      # cents_to_brl, audit_flag, log_run_results
├── tests/                       # singular + generic/ (teste customizado)
└── .github/workflows/dbt_ci.yml # CI: dbt build + SQLFluff
```
