# bi-toll-analytics — dashboard (BI) com Evidence.dev

A **"última milha"**: um painel executivo lendo os marts `gold` do dbt e
publicado como **site estático** (combina com o stack: SQL → site, igual ao dbt docs).
Construído com **[Evidence.dev](https://evidence.dev)** sobre o DuckDB.

```
DuckDB (marts do dbt)  ──[Evidence: SQL]──▶  site estático (HTML/JS)  ──▶  GitHub Pages
```

## O que mostra ([pages/index.md](pages/index.md))
- Transações **suspeitas por flag** (BarChart) — de `audit_suspect_transactions`.
- **Receita por praça** (BarChart) — de `agg_daily_revenue_by_plaza`.
- **Scorecard por praça** (taxa de suspeita + z-score) — do Python model `py_plaza_audit_stats`.

As consultas ficam em [sources/toll/](sources/toll) (DuckDB) e são referenciadas nas páginas.

## Rodar
```bash
# precisa do DuckDB do dbt construído (ingestão + dbt build no projeto upstream)
npm install
npm run sources    # materializa as queries a partir do DuckDB
npm run dev        # http://localhost:3000  (ou: npm run build -> site estático em ./build)
```

## Hospedagem
- **GitHub Pages** (automático): o workflow `pages_site.yml` builda o dbt + o Evidence e
  publica **um site combinado** — dashboard em `/` e **lineage do dbt em `/lineage/`**.
- O `deployment.basePath` (em `evidence.config.yaml`) já aponta para o subpath do
  repositório (`/toll-analytics-platform`).
- Alternativa: **Evidence Cloud** (1-clique a partir do repo, grátis para projetos públicos).

> Pré-requisito: o DuckDB com os marts (gerado por ingestão + `dbt build` do upstream).
> Em produção, basta apontar o `connection.yaml` para o warehouse (Databricks/Snowflake).
