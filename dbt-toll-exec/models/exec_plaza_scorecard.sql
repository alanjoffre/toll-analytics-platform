-- Scorecard executivo por praça: combina DOIS produtos PÚBLICOS do projeto
-- upstream (toll_analytics) via cross-project ref (dbt Mesh):
--   - agg_daily_revenue_by_plaza (receita)
--   - audit_suspect_transactions (suspeitas)
with revenue as (
    select
        plaza_id,
        round(sum(revenue_brl), 2) as revenue_brl
    from {{ ref('toll_analytics', 'agg_daily_revenue_by_plaza') }}
    group by plaza_id
),

suspects as (
    select
        plaza_id,
        count(*) as suspect_count
    from {{ ref('toll_analytics', 'audit_suspect_transactions') }}
    group by plaza_id
)

select
    r.plaza_id,
    r.revenue_brl,
    coalesce(s.suspect_count, 0) as suspect_count
from revenue as r
left join suspects as s on r.plaza_id = s.plaza_id
order by r.revenue_brl desc
