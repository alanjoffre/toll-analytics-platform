---
title: Auditoria de Pedágio — Painel Executivo
---

Painel construído com **Evidence.dev** (SQL → site estático) lendo os marts `gold`
do dbt no DuckDB. Dados sintéticos. · Lineage do dbt publicado junto, em `/lineage/`.

## Transações suspeitas por tipo

```sql audit
select * from toll.audit_by_flag
```

<BarChart data={audit} x=audit_flag y=n title="Suspeitas por flag de auditoria" />

## Receita por praça

```sql revenue
select * from toll.revenue_by_plaza
```

<BarChart data={revenue} x=plaza_id y=revenue_brl title="Receita (BRL) por praça" />

## Scorecard por praça (taxa de suspeita + z-score)

```sql scorecard
select * from toll.plaza_scorecard
```

<DataTable data={scorecard}>
  <Column id=plaza_id title="Praça" />
  <Column id=total_transactions title="Transações" />
  <Column id=suspect_transactions title="Suspeitas" />
  <Column id=suspect_rate title="Taxa" fmt="0.0%" />
  <Column id=suspect_rate_zscore title="z-score" />
</DataTable>
