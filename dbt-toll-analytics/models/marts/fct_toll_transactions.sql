{{
    config(
        materialized='incremental',
        unique_key='transaction_id',
        on_schema_change='append_new_columns'
    )
}}

-- fct_toll_transactions — tabela-fato (grão = 1 transação).
-- INCREMENTAL: em escala, só processa o que chegou DEPOIS da última carga.
-- unique_key garante idempotência (re-rodar não duplica).

with enriched as (
    select * from {{ ref('int_transactions_enriched') }}

    {% if is_incremental() %}
    -- LOOKBACK contra LATE-ARRIVING DATA: em vez de "> max(event_date)" (que
    -- descartaria PARA SEMPRE uma transação que chega atrasada), reprocesso a
    -- janela dos últimos N dias. O unique_key (merge) deduplica o reprocessamento,
    -- então não há risco de duplicar. Trade-off documentado no ADR-8.
    -- (DuckDB: date - inteiro = date, subtrai N dias.)
        where event_date >= (
            select coalesce(max(event_date), cast('1900-01-01' as date)) - {{ var('incremental_lookback_days', 3) }}
            from {{ this }}
        )
    {% endif %}
)

select
    transaction_sk,
    transaction_id,
    cast(strftime(event_date, '%Y%m%d') as integer)                                     as date_key,
    event_ts,
    event_date,
    vehicle_id,
    plaza_id,
    category,
    payment_method,
    status,
    is_duplicate,
    amount_cents,
    expected_amount_cents,
    amount_diff_cents,
    {{ cents_to_brl('amount_cents') }}          as amount_brl,
    {{ cents_to_brl('expected_amount_cents') }} as expected_brl,
    -- mesma regra de negócio do produto de auditoria (macro reutilizada = DRY),
    -- materializada no fato para habilitar métricas no Semantic Layer.
    {{ audit_flag('status', 'amount_cents', 'expected_amount_cents', 'is_duplicate') }} as audit_flag
from enriched
