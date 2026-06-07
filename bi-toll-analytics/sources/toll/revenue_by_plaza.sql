select plaza_id, round(sum(revenue_brl), 2) as revenue_brl
from main.agg_daily_revenue_by_plaza
group by 1 order by revenue_brl desc
