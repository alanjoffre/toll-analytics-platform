-- rpt_plaza_revenue v2 — versão atual (latest_version). Adiciona o ticket médio.
-- Quebra de contrato (coluna nova) feita via VERSÃO, não in-place: consumidores
-- migram no seu ritmo até a v1 ser removida na deprecation_date.
select
    plaza_id,
    {{ cents_to_brl("sum(amount_cents) filter (where status = 'COMPLETED' and amount_cents > 0)") }} as revenue_brl,
    {{ cents_to_brl("avg(amount_cents) filter (where status = 'COMPLETED' and amount_cents > 0)") }} as avg_ticket_brl
from {{ ref('fct_toll_transactions') }}
group by plaza_id
