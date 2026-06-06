select audit_flag, count(*) as n
from {{ ref('toll_analytics', 'audit_suspect_transactions') }}
group by 1
