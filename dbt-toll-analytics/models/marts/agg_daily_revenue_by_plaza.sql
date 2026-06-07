-- agg_daily_revenue_by_plaza — receita diária por praça.
-- (PR de teste do Slim CI — mudança trivial p/ exercitar state:modified+)
-- Receita conta SÓ cobranças legítimas (status COMPLETED e valor > 0);
-- transações em falha / valor inválido não entram na receita.

with fct as (
    select * from {{ ref('fct_toll_transactions') }}
)

select
    event_date,
    plaza_id,
    count(*)
        as total_transactions,
    count(*) filter (where status = 'COMPLETED' and amount_cents > 0)
        as billable_transactions,
    -- DINHEIRO EM CENTAVOS INTEIROS: somo amount_cents (exato) e converto para BRL só
    -- no final. Somar reais já arredondados (amount_brl) acumularia erro de
    -- arredondamento/float — anti-padrão em dado financeiro. Ver ADR-15.
    {{ cents_to_brl("sum(amount_cents) filter (where status = 'COMPLETED' and amount_cents > 0)") }} as revenue_brl
from fct
group by event_date, plaza_id
order by event_date, plaza_id
