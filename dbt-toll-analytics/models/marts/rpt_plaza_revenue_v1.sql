-- rpt_plaza_revenue v1 — DEPRECADA (deprecation_date no _marts.yml).
-- Receita por praça. Mantida para consumidores legados até a data de deprecação.
select
    plaza_id,
    {{ cents_to_brl("sum(amount_cents) filter (where status = 'COMPLETED' and amount_cents > 0)") }} as revenue_brl
from {{ ref('fct_toll_transactions') }}
group by plaza_id
