select plaza_id, total_transactions, suspect_transactions, suspect_rate, suspect_rate_zscore
from main.py_plaza_audit_stats
order by suspect_rate desc
