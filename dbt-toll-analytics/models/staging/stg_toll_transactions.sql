with source as (
    select * from {{ ref('raw_toll_transactions') }}
),

typed as (
    select
        cast(transaction_id as varchar) as transaction_id,
        cast(vehicle_id as varchar)     as vehicle_id,
        cast(plaza_id as varchar)       as plaza_id,
        cast(event_ts as timestamp)     as event_ts,
        cast(event_ts as date)          as event_date,
        cast(amount_cents as integer)   as amount_cents,   -- nulo/zero é MANTIDO (flag, não delete)
        upper(trim(payment_method))     as payment_method,
        upper(trim(status))             as status
    from source
),

-- Dedup determinístico: a duplicata exata de transaction_id (T0020) colapsa em 1 linha.
deduped as (
    select
        *,
        row_number() over (
            partition by transaction_id
            order by event_ts
        ) as _rn
    from typed
)

select
    -- surrogate key técnica (desacopla a chave do negócio) — padrão em DW
    {{ dbt_utils.generate_surrogate_key(['transaction_id']) }} as transaction_sk,
    transaction_id,
    vehicle_id,
    plaza_id,
    event_ts,
    event_date,
    amount_cents,
    payment_method,
    status
from deduped
where _rn = 1
