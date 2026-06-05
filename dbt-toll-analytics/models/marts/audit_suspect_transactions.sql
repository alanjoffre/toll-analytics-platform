-- audit_suspect_transactions — O PRODUTO DE DADOS.
-- Aplica a regra de negócio (macro audit_flag) e entrega SÓ o que precisa de
-- atenção (flag != OK). Regra de auditoria: FLAG, não DELETE — nada some.

with enriched as (
    select * from {{ ref('int_transactions_enriched') }}
),

classified as (
    select
        transaction_id,
        event_ts,
        event_date,
        plaza_id,
        plaza_name,
        vehicle_id,
        plate_masked,
        category,
        category_description,
        status,
        payment_method,
        is_duplicate,
        amount_cents,
        expected_amount_cents,
        amount_diff_cents,
        {{ cents_to_brl('amount_cents') }}          as amount_brl,
        {{ cents_to_brl('expected_amount_cents') }} as expected_brl,
        {{ audit_flag('status', 'amount_cents', 'expected_amount_cents', 'is_duplicate') }} as audit_flag
    from enriched
)

select *
from classified
where audit_flag <> 'OK'
order by event_ts
