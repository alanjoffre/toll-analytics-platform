select audit_flag, count(*) as n
from main.audit_suspect_transactions
group by 1 order by n desc
