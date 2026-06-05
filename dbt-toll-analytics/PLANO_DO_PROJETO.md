# PLANO DO PROJETO — dbt-toll-analytics (nível Sênior)

> **Este arquivo é o cérebro do projeto.** Ele é autossuficiente: explica O QUE
> vamos construir, POR QUE cada técnica importa (didático) e COMO aplicar aqui.
> Foi escrito para você **fechar a guia atual e abrir uma nova sessão focada só
> neste projeto** — basta abrir esta pasta e pedir para continuar a partir daqui.

---

## 0. Como retomar numa nova sessão (leia primeiro)

1. Abra a pasta `dbt-toll-analytics/` numa nova conversa.
2. Diga ao assistente: *"Leia o PLANO_DO_PROJETO.md e continue construindo o
   projeto seguindo a Ordem de Construção (seção 9), a partir do status atual
   (seção 11). Explique cada passo enquanto faz."*
3. Ao final, rode a validação real (seção 10): `dbt build`.

**Objetivo de carreira por trás disto:** sair de "sei a mecânica do dbt" (júnior/
pleno) para "sei **engenharia de dados com dbt em produção**" (sênior) — que é o
que justifica faixa salarial maior e segura entrevista. Cada técnica abaixo tem
uma **"fala de entrevista"** associada (seção 12).

---

## 1. O que é o projeto (em 3 linhas)

Um **produto de dados de auditoria de vale-pedágio**: ingere transações de pedágio
cruas, limpa/modela em camadas e entrega (a) marts analíticos confiáveis e (b) um
modelo de **auditoria** que sinaliza transações suspeitas (tarifa divergente,
cobrança em falha, valor inválido, duplicidade). Tudo com **dados sintéticos**
(nenhum dado real de cliente), rodando **localmente em DuckDB** e **portável para
Databricks** trocando 1 arquivo de conexão.

**Por que esse domínio?** É próximo de trabalho real de engenharia de dados
(mobilidade/pagamentos) sem expor nada confidencial — ótimo para portfólio.

---

## 2. Por que dbt + DuckDB (e a ponte para Databricks)

- **dbt (data build tool)** é o padrão de mercado para a camada de **transformação**
  (o "T" do ELT): você escreve **SQL modular** que roda dentro do banco/lakehouse,
  com práticas de engenharia de software — versionamento (Git), **testes**,
  **documentação + lineage**, modularidade e reaproveitamento.
- **DuckDB**: banco analítico que roda em 1 arquivo local, **sem nuvem e sem custo**.
  Perfeito para aprender e demonstrar. O fluxo dbt é **idêntico** ao do Databricks.
- **Ponte Databricks**: trocando o `profiles.yml` (adapter `dbt-databricks`), os
  mesmos modelos SQL rodam em **Delta Lake + Unity Catalog**. (Detalhe na seção 8.)

---

## 3. Conceitos fundamentais do dbt (didático)

| Conceito | O que é | Como usamos aqui |
|---|---|---|
| **model** | Um arquivo `.sql` com um `SELECT`. O dbt cria a view/tabela a partir dele. | Cada `stg_*`, `int_*`, `dim_*`, `fct_*`, `agg_*`, `audit_*`. |
| **`ref()`** | Referência a outro model/seed. Cria o **DAG** (grafo de dependências) e a ordem de execução automática. | `from {{ ref('stg_toll_transactions') }}`. |
| **`source()`/seed** | Dados de entrada. *Seed* = CSV versionado que o dbt carrega. | Nossos CSVs em `seeds/` = camada bronze. |
| **materialização** | Como o model vira objeto no banco: `view` (consulta salva), `table` (materializada), `incremental` (atualiza só o novo), `ephemeral` (CTE inline). | staging/intermediate = `view`; marts = `table`; `fct_*` = `incremental`. |
| **DAG / lineage** | Grafo de dependências entre models, gerado pelos `ref()`. | `dbt docs` desenha o lineage de ponta a ponta. |
| **teste** | Asserção sobre os dados (genérico) ou sobre a lógica (unit test). | unique, not_null, relationships, accepted_values + custom + unit tests. |
| **macro** | Função Jinja reutilizável que gera SQL. | `cents_to_brl`, `audit_flag`, `log_run_results`. |
| **package** | Biblioteca dbt externa. | `dbt_utils`, `dbt_expectations`. |
| **snapshot** | Captura histórico de mudanças (SCD2) ao longo do tempo. | `snap_toll_plazas` (demonstra a técnica). |
| **exposure** | Declara um consumidor downstream (dashboard/relatório) no lineage. | "Relatório de auditoria aos gestores". |
| **contract** | "Contrato de dados": trava colunas/tipos do model (falha se divergir). | nos marts gold (`fct`, `dim_*`). |

---

## 4. Arquitetura — Medallion mapeado em camadas dbt

```
            BRONZE                SILVER                     GOLD
        (dados crus)        (limpo/tipado/PII)      (modelado p/ consumo)

 seeds/ ───────────►  models/staging/ ──────►  models/intermediate/ ──►  models/marts/
  raw_toll_plazas       stg_toll_plazas           int_transactions_       dim_plaza
  raw_fare_schedule     stg_fare_schedule           enriched              dim_vehicle
  raw_vehicles          stg_vehicles            (joins + tarifa           dim_date
  raw_vehicle_          stg_vehicle_              point-in-time +         fct_toll_transactions
    categories            categories               diferença +           agg_daily_revenue_by_plaza
  raw_toll_             stg_toll_transactions       duplicidade)          audit_suspect_transactions ◄── PRODUTO
    transactions        (dedup, masking PII)                              (+ snapshot, exposure)
```

- **Bronze (seeds):** dados crus, inclusive **imperfeições propositais** (ver §6).
- **Silver (staging):** 1 model por fonte. Tipagem, limpeza, **dedup**, **masking de
  PII** (placa). Regra: staging **não** faz join entre fontes — só "arruma a casa".
- **Gold (intermediate + marts):** intermediate faz o enriquecimento (joins +
  regra de negócio); marts entrega o modelo **dimensional** (fatos/dimensões),
  agregações e o **produto de auditoria**.

---

## 5. Modelo de dados (entidades)

- **toll_plazas** — praças de pedágio (id, nome, rodovia, UF).
- **fare_schedule** — **tabela de tarifas com vigência** (`plaza_id, fare_cents,
  valid_from, valid_to`). É aqui que mora o histórico de preço (SCD2-style).
- **vehicles** — veículos (id, placa→mascarada, categoria, conta).
- **vehicle_categories** — categoria → `fare_multiplier` (eixos). Ex.: cat 2 (carro)
  = 1.0×, cat 4 = 2.0×, cat 6 = 3.0×, cat 9 (carreta) = 4.5×.
- **toll_transactions** — passagens (id, veículo, praça, timestamp, valor cobrado,
  forma de pagamento, status).

**Tarifa esperada de uma transação** =
`fare_cents (vigente na data do evento) × fare_multiplier (da categoria do veículo)`.

---

## 6. Dados sintéticos: as imperfeições propositais (a "graça" do projeto)

Os seeds contêm erros de propósito para exercitar limpeza + auditoria:

| Caso | Linha(s) no seed | O que demonstra |
|---|---|---|
| **Duplicata exata** de `transaction_id` | `T0020` repetido | **Dedup** na staging (teste `unique` passa depois). |
| **Valor nulo** | `T0026` (amount vazio) | Auditoria flag `VALOR_INVALIDO` (sem quebrar `not_null` — ver nota). |
| **Valor zero** | `T0010` | Flag `VALOR_INVALIDO`. |
| **Cobrança em falha** | `T0009` (FAILED), `T0018` (REVERSED) com valor > 0 | Flag `COBRANCA_EM_FALHA`. |
| **Tarifa divergente** | `T0007` (overcharge), `T0022` (undercharge) | Flag `TARIFA_DIVERGENTE`. |
| **Duplicidade na janela** | `T0015` + `T0016` (mesmo veículo+praça em 3 min) | Flag `POSSIVEL_DUPLICIDADE`. |
| **Mudança de tarifa no meio da janela** | praça `P003` muda de 990→1050 em 2026-05-03 | **Point-in-time** (ver §7). |

> **Nota de design (sênior):** valor nulo/zero **não** é removido nem quebra teste —
> é **mantido e sinalizado** pelo modelo de auditoria. Em auditoria, a regra é
> *flag, não delete*. Por isso `not_null` fica só nas chaves, e o valor é tratado
> como regra de negócio no produto.

---

## 7. A técnica-estrela: tarifa **point-in-time** (correção temporal)

**Problema:** o preço do pedágio muda no tempo. Se eu comparar uma transação
**antiga** contra a tarifa **atual**, gero **falso positivo** de "tarifa divergente".

**Solução:** juntar a transação à `fare_schedule` pela **data do evento**
(`event_date BETWEEN valid_from AND valid_to`) — a tarifa **vigente naquele dia**.

**Exemplo numérico (está nos seeds):** praça P003, carreta (cat 9, ×4.5):
- Tarifa válida até 2026-05-02 = **990**; a partir de 2026-05-03 = **1050**.
- `T0006` (P003, **01/05**, valor 4455): esperado = 990×4.5 = **4455** → **OK**.
  - Se eu usasse a tarifa atual (1050): 1050×4.5 = 4725 → marcaria **errado** como divergente. ❌
- `T0023` (P003, **03/05**, valor 4455): esperado = 1050×4.5 = **4725** → **DIVERGENTE** (correto). ✔

> Isto é exatamente o que separa um modelo júnior (join na tarifa atual) de um
> sênior (join **point-in-time**). É o destaque do projeto.

---

## 8. Plano por fases — cada item: O QUE · POR QUE · COMO · ARQUIVO

### 🟢 FASE 1 — Núcleo (base sólida)

1. **Camadas staging (silver)** — *O QUE:* 1 model por fonte, tipado/limpo.
   *POR QUE:* isola "arrumação" do resto; reaproveitável. *COMO:* `cast`, `trim`,
   `upper`, dedup por `row_number()`, **masking de PII** na placa.
   *ARQUIVOS:* `models/staging/stg_*.sql`, `_staging.yml`.
2. **Dimensões** — *O QUE:* `dim_plaza`, `dim_vehicle`, `dim_date`.
   *POR QUE:* modelagem dimensional (star schema) = consumo fácil/perf. *COMO:*
   `dim_date` via `dbt_utils.date_spine`. *ARQUIVOS:* `models/marts/dim_*.sql`.
3. **Fato + agregação** — `fct_toll_transactions`, `agg_daily_revenue_by_plaza`.
4. **Produto de auditoria** — `audit_suspect_transactions` com `audit_flag`.
5. **Testes genéricos + macro + docs** — unique/not_null/relationships/
   accepted_values; macro `cents_to_brl`; descrições em todos os `.yml`.

### 🟡 FASE 2 — Sobe para sênior (modelagem + escala)

6. **SCD2 / histórico de tarifa (point-in-time)** — *O QUE:* `fare_schedule` com
   vigência + join temporal. *POR QUE:* correção temporal (§7), evita falso
   positivo. *ARQUIVOS:* `seeds/raw_fare_schedule.csv`, `stg_fare_schedule.sql`,
   usado em `int_transactions_enriched.sql`.
7. **Snapshot (dbt)** — *O QUE:* `snap_toll_plazas` captura mudanças de atributo.
   *POR QUE:* demonstra a técnica de **CDC/SCD2 nativa** do dbt para mudanças
   *futuras*. *COMO:* `snapshots/` com `strategy=check`. *Nota honesta:* snapshot
   constrói histórico **ao longo de várias execuções**; para histórico
   determinístico usamos a `fare_schedule` (seed). Documentar essa decisão (ADR).
8. **Model incremental** — *O QUE:* `fct_toll_transactions` materializado como
   `incremental`. *POR QUE:* em escala, não reprocessa tudo — só o novo. *COMO:*
   `unique_key='transaction_id'`, filtro `is_incremental()` por data.
9. **Surrogate keys** — *O QUE:* chaves técnicas via `dbt_utils.generate_surrogate_key`.
   *POR QUE:* desacopla a chave do negócio; padrão em DW. *COMO:* nas dims/fato.
10. **Model contracts** — *O QUE:* trava colunas + tipos dos marts gold. *POR QUE:*
    **contrato de dados** — quebra o build se o schema mudar sem querer. *COMO:*
    `+contract: {enforced: true}` + `columns/data_type` no `_marts.yml`.
11. **Teste genérico customizado + dbt_expectations** — *O QUE:* teste reusável
    "nenhuma cobrança em transação FAILED" + `accepted_range`/`expression_is_true`.
    *POR QUE:* Data Quality como sistema, não ad-hoc.

### 🟠 FASE 3 — Sênior "de produção" (o diferencial)

12. **Unit tests (dbt 1.8+)** — *O QUE:* testo a **lógica** do `audit_flag` com
    inputs **mockados** e saída esperada. *POR QUE:* prova que a regra funciona,
    determinístico (pouquíssimo portfólio tem). *ARQUIVO:* `models/marts/_unit_tests.yml`.
13. **Observabilidade** — *O QUE:* `store_failures` (materializa linhas que falham)
    + hook `on-run-end` gravando metadados em `_audit_runs`. *POR QUE:*
    monitoramento de pipeline. *ARQUIVO:* `macros/log_run_results.sql`.
14. **CI/CD (GitHub Actions)** — *O QUE:* em PR, roda `dbt build` (DuckDB) +
    **SQLFluff** (lint de SQL). *POR QUE:* qualidade automatizada = produção.
    *ARQUIVOS:* `.github/workflows/dbt_ci.yml`, `.sqlfluff`. *Conceito:* mencionar
    **Slim CI** (`state:modified+` com deferral) como padrão em projetos grandes.
15. **Severidade de testes + Exposures** — `warn` × `error` com racional;
    `exposures.yml` declara o "Relatório de auditoria aos gestores" no lineage.
16. **ADRs no README** — *O QUE:* registro das decisões (por que incremental, por
    que SCD2 via seed, por que cada escolha). *POR QUE:* **julgamento documentado**
    é o que mais sinaliza senioridade.

---

## 9. Ordem de construção (build order recomendada)

> Construir respeitando o DAG (de baixo p/ cima) e validando a cada bloco.

1. **Config:** `dbt_project.yml`, `profiles.yml`, `packages.yml`, `requirements.txt`,
   `.gitignore`, `.sqlfluff`. → `dbt deps`
2. **Seeds (bronze):** os 5 CSVs + `_seeds.yml`. → `dbt seed`
3. **Staging (silver):** `stg_*` + `_staging.yml`. → `dbt run -s staging` + `dbt test -s staging`
4. **Snapshot:** `snap_toll_plazas`. → `dbt snapshot`
5. **Intermediate:** `int_transactions_enriched` (+ point-in-time + duplicidade).
6. **Macros:** `cents_to_brl`, `audit_flag`, `log_run_results`.
7. **Marts (gold):** `dim_date`, `dim_plaza`, `dim_vehicle`, `fct_toll_transactions`
   (incremental + contract), `agg_daily_revenue_by_plaza`, `audit_suspect_transactions`.
8. **Testes:** genéricos (`_marts.yml`), customizado (`tests/generic/`), singular
   (`tests/`), **unit tests** (`_unit_tests.yml`). → `dbt test`
9. **Exposures** (`exposures.yml`).
10. **CI** (`.github/workflows/dbt_ci.yml`) + `.sqlfluff`.
11. **README** com ADRs + instruções.
12. **Validação final:** `dbt build` (seed+run+test+snapshot) verde.

---

## 10. Como rodar e validar (local)

```bash
cd dbt-toll-analytics
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
dbt deps    --profiles-dir .
dbt build   --profiles-dir .          # seed + run + snapshot + test, tudo
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .   # lineage
```
Conferir resultados:
```bash
python -c "import duckdb; c=duckdb.connect('toll_analytics.duckdb'); \
print(c.sql('select audit_flag, count(*) from main_marts.audit_suspect_transactions group by 1'))"
```
> Observação: o schema dos marts pode aparecer como `main` ou `main_marts`
> dependendo da config de schema do dbt-duckdb — ajustar o `select` conforme.

---

## 11. STATUS ATUAL (onde retomar)

> **✅ PROJETO CONCLUÍDO + HARDENING SÊNIOR.** `dbt build` valida verde:
> `PASS=92 WARN=1 ERROR=0` (o WARN é intencional — ver ADR-6 no README).
> Auditoria entrega 9 transações suspeitas (3 TARIFA_DIVERGENTE, 2 VALOR_INVALIDO,
> 2 POSSIVEL_DUPLICIDADE, 2 COBRANCA_EM_FALHA). Point-in-time validado (T0006 OK,
> T0023 divergente). Fato incremental idempotente (26 linhas após dedup).
>
> **Rodada de correções (Tier 1 — bugs reais) + diferenciais aplicados:**
> 1. Fan-out no join point-in-time travado com `mutually_exclusive_ranges` (ADR-9).
> 2. Late-arriving data: incremental agora com janela de **lookback** (ADR-8).
> 3. `dim_date` deixou de ser fixa em 2026 — faixa derivada dos dados (ADR-10).
> 4. **Semantic Layer (MetricFlow)**: métricas `revenue`, `suspect_rate`,
>    `revenue_leakage_brl` etc. — validado com `mf query` real (ADR-11, ADR-12).
> 5. Ambientes **dev/prod** no `profiles.yml`.
> 6. README ganhou seção **"Limitações conhecidas e roadmap"** (o movimento meta).
> 7. **sources + source freshness** (contrato de ingestão) — `_sources.yml`, ADR-13;
>    `dbt source freshness` validado (WARN esperado contra o seed estático).
> 8. **Elementary** (observabilidade de dados) — pacote + `volume_anomalies` + schema
>    `elementary`; in-warehouse funciona no DuckDB (ADR-14). `dbt build` agora PASS=125.
>    Ressalva: relatório HTML do `edr` tem suporte áspero no DuckDB.
> 9. **Correção financeira (ADR-15):** receita agregada em centavos inteiros (não float)
>    no agg e no Semantic Layer. **CI endurecido:** lint de models+tests+snapshots+macros
>    (todo verde via `sqlfluff fix`), cache de pip, `dbt docs generate` + artefato.
> 10. **ADR-16:** testes migrados para o formato `arguments:` (zero deprecation no `dbt parse`).
> 11. **ADR-17:** Elementary/anomalia como job AGENDADO (`tag:observability`); CI de PR roda
>     `dbt build --exclude tag:observability` (determinístico, **PASS=124**); workflow
>     `observability.yml` roda a detecção de anomalia com histórico acumulado.
> Roadmap futuro: orquestração (Airflow+Cosmos) → publicar docs no GitHub Pages → Slim CI.
> O histórico abaixo fica como registro do ponto de partida desta sessão.

**✅ Já criados:**
- `dbt_project.yml` (já no formato sênior: vars, on-run-end, store_failures, snapshots)
- `profiles.yml`, `packages.yml` (dbt_utils), `requirements.txt`, `.gitignore`
- `README.md` (versão inicial — **reescrever** com ADRs na Fase 3)
- Seeds: `raw_toll_plazas.csv`, `raw_vehicles.csv`, `raw_vehicle_categories.csv`,
  `raw_toll_transactions.csv`, `seeds/_seeds.yml`
- Staging: `stg_toll_plazas.sql`, `stg_vehicle_categories.sql`, `stg_vehicles.sql`

**⏳ Pendentes (a fazer, nesta ordem):**
- [ ] Ajustar `packages.yml` → adicionar `dbt_expectations`
- [ ] Ajustar `requirements.txt` → adicionar `sqlfluff` (+ `sqlfluff-templater-dbt`)
- [ ] `seeds/raw_toll_plazas.csv` → **remover** `base_fare_cents` (tarifa vai p/ schedule)
- [ ] `seeds/raw_fare_schedule.csv` (NOVO — SCD2 de tarifa, com a mudança da P003)
- [ ] `stg_toll_plazas.sql` → remover fare; `stg_fare_schedule.sql` (NOVO)
- [ ] `stg_toll_transactions.sql` (NOVO — dedup + tipos + surrogate key)
- [ ] `models/staging/_staging.yml` (testes + docs)
- [ ] `snapshots/snap_toll_plazas.sql`
- [ ] `models/intermediate/int_transactions_enriched.sql` (+ `_intermediate.yml`)
- [ ] `macros/cents_to_brl.sql`, `macros/audit_flag.sql`, `macros/log_run_results.sql`
- [ ] `models/marts/`: `dim_date.sql`, `dim_plaza.sql`, `dim_vehicle.sql`,
      `fct_toll_transactions.sql`, `agg_daily_revenue_by_plaza.sql`,
      `audit_suspect_transactions.sql`, `_marts.yml` (contracts+testes), `_unit_tests.yml`
- [ ] `models/exposures.yml`
- [ ] `tests/generic/test_not_charged_when_failed.sql`, `tests/assert_unique_transaction_in_fct.sql`
- [ ] `.sqlfluff`, `.github/workflows/dbt_ci.yml`
- [ ] **Reescrever `README.md`** com ADRs (seção de decisões)
- [ ] **Validar:** `dbt deps && dbt build` verde

---

## 12. Mapa "técnica → fala de entrevista" (use no LinkedIn e na conversa)

| Técnica no projeto | O que dizer |
|---|---|
| Point-in-time tariff (SCD2 via schedule) | "Modelei tarifa com vigência e join point-in-time pra evitar falso positivo em transações históricas." |
| Model incremental | "Materializei o fato como incremental com unique_key pra não reprocessar histórico em escala." |
| Model contracts | "Apliquei contratos de dados nos marts — o build quebra se o schema mudar sem querer." |
| Unit tests (1.8) | "Cobri a lógica de auditoria com unit tests e inputs mockados, além dos testes de dados." |
| store_failures + on-run-end | "Tenho observabilidade: materializo falhas de teste e gravo metadados de execução." |
| CI + SQLFluff + Slim CI | "PR roda dbt build + lint; em projeto grande, Slim CI com state:modified e deferral." |
| Masking de PII | "Mascaro PII (placa) já na silver, por LGPD/menor exposição." |
| Exposures | "Declaro o consumidor downstream (relatório de auditoria) no lineage." |

---

## 13. Portabilidade para Databricks (o seu stack real)

Trocar só o `profiles.yml` (adapter `dbt-databricks`, Unity Catalog + Delta).
Equivalências:
- materialização `table`/`incremental` → tabelas **Delta** (incremental usa `MERGE`).
- performance: **liquid clustering** / `ZORDER` no lugar dos índices.
- `catalog`/`schema` = Unity Catalog.
- seeds → na prática viriam de tabelas de ingestão (Auto Loader/COPY INTO), não CSV.

Os **models SQL são os mesmos**. É isso que torna o aprendizado local 100%
transferível para o trabalho real.

> **Concretizado:** o target `prod` do `profiles.yml` **já é Databricks** (não mais um
> DuckDB placeholder) — `type: databricks`, Unity Catalog, `env_var` com default para o
> `dev` nunca quebrar. Adapter em `requirements-databricks.txt`. (Ver ADR-7.)

---

## 14. Orquestração — Airflow + Astronomer Cosmos (projeto irmão)

A camada de **transformação** (este projeto) é orquestrada por um projeto separado,
[`../airflow-toll-analytics`](../airflow-toll-analytics), com **Cosmos**: cada nó do dbt
(model/seed/snapshot/test) vira **uma task** do Airflow — lineage real, não um `dbt build`
monolítico. Pipeline: `source_freshness` (gate) → `transform` (Cosmos) → `generate_docs`,
com schedule cron, retries+backoff, SLA, alerta on-failure e um DAG separado de
observabilidade.

**Validado ponta-a-ponta** (`airflow dags test` num DuckDB do zero): `state=success`,
0 locks, 0 tracebacks, auditoria com as 9 suspeitas esperadas; teste de integridade de
DAG no CI (`pytest`) verde.

### ADRs da orquestração (prefixo `A` para separar da camada dbt)

- **ADR-A1 — dbt fora do ambiente do Airflow.** O Airflow chama o dbt do venv do próprio
  projeto dbt (`DBT_EXECUTABLE_PATH`, `InvocationMode.SUBPROCESS`). *Por quê:* Airflow e
  dbt têm pins conflitantes; isolar evita o "dependency hell" e mantém uma fonte de
  verdade do dbt. *Trade-off:* um venv a mais, em troca de zero conflito.
- **ADR-A2 — DuckDB single-writer → serialização.** DuckDB é embarcado (1 escritor). Duas
  defesas: (1) **pool do Airflow com 1 slot** (`duckdb_serial`) nas tasks dbt; (2) nas runs
  de orquestração o DuckDB grava num caminho **local** (`/tmp`, via `DBT_DUCKDB_PATH`), não
  no arquivo do OneDrive — o FS sincronizado atrasava a liberação do lock. *Por quê:*
  concorrência num arquivo único corrompe/trava. *Nota:* em Databricks/Snowflake a
  concorrência é nativa e o pool sai — o lock é artefato do DuckDB, não do design.
- **ADR-A3 — testes com `TestBehavior.AFTER_ALL` + observabilidade isolada.** Os testes
  rodam **depois** de todos os models (não AFTER_EACH): num DB limpo, um teste de
  `relationships` referencia tabela de outro model que talvez ainda não exista — AFTER_ALL
  garante a ordem. E a detecção de anomalia (Elementary, `tag:observability`) fica num DAG
  agendado próprio, fora do caminho crítico (mesmo racional do ADR-17). *Trade-off:* menos
  granularidade nas tasks de teste, em troca de corretude num first-run.

> Resumo honesto: os atritos resolvidos aqui (lock, ordem de teste, deps) são **específicos
> do stack local DuckDB+Cosmos**. Documentá-los — e saber que somem no warehouse — é o que
> mostra julgamento de engenharia.

---

*Fim do plano. Próximo passo numa nova sessão: seguir a §9 a partir da §11.*
