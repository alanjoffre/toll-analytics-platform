{{ config(materialized='ephemeral') }}

-- EPHEMERAL — detecção de DUPLICIDADE na janela (var duplicate_window_seconds).
-- Não vira objeto no banco: o dbt inlina este SELECT como CTE em quem der ref().
-- Uso certo de ephemeral: um passo lógico reutilizável, barato, que não precisa
-- ser materializado nem consultado isoladamente. Mantém o int_transactions_enriched
-- mais limpo (separa "achar duplicata" de "enriquecer").

with transactions as (
    select * from {{ ref('stg_toll_transactions') }}
),

-- olho a passagem anterior E a próxima do MESMO veículo na MESMA praça
dup_check as (
    select
        *,
        date_diff(
            'second',
            lag(event_ts) over (partition by vehicle_id, plaza_id order by event_ts),
            event_ts
        ) as secs_since_prev,
        date_diff(
            'second',
            event_ts,
            lead(event_ts) over (partition by vehicle_id, plaza_id order by event_ts)
        ) as secs_to_next
    from transactions
)

select
    *,
    coalesce(secs_since_prev between 0 and {{ var('duplicate_window_seconds') }}, false)
    or coalesce(secs_to_next between 0 and {{ var('duplicate_window_seconds') }}, false)
        as is_duplicate
from dup_check
