with transactions as (
    select * from {{ ref('stg_toll_transactions') }}
),

vehicles as (
    select * from {{ ref('stg_vehicles') }}
),

categories as (
    select * from {{ ref('stg_vehicle_categories') }}
),

plazas as (
    select * from {{ ref('stg_toll_plazas') }}
),

fares as (
    select * from {{ ref('stg_fare_schedule') }}
),

-- 1) Detecção de DUPLICIDADE na janela: olho a passagem anterior E a próxima
--    do MESMO veículo na MESMA praça. Se qualquer uma cair dentro da janela
--    (var duplicate_window_seconds), marco ESTA como possível duplicidade —
--    assim AMBAS as linhas do par ficam sinalizadas (T0015 + T0016).
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
),

flagged_dup as (
    select
        *,
        coalesce(secs_since_prev between 0 and {{ var('duplicate_window_seconds') }}, false)
        or coalesce(secs_to_next between 0 and {{ var('duplicate_window_seconds') }}, false)
            as is_duplicate
    from dup_check
),

enriched as (
    select
        t.transaction_sk,
        t.transaction_id,
        t.event_ts,
        t.event_date,
        t.amount_cents,
        t.payment_method,
        t.status,
        t.is_duplicate,

        -- dimensões descritivas
        t.vehicle_id,
        v.plate_masked,
        v.account_id,
        v.category,
        c.description                                                             as category_description,
        c.fare_multiplier,

        t.plaza_id,
        p.plaza_name,
        p.highway,
        p.uf,

        -- 2) TARIFA POINT-IN-TIME: a tarifa vigente NA DATA do evento.
        --    É o que evita falso positivo de "tarifa divergente" em transações
        --    históricas (ver §7 do PLANO). LEFT JOIN: sem schedule -> sem
        --    esperado -> não acusa divergência (conservador).
        f.fare_cents,
        cast(round(f.fare_cents * c.fare_multiplier) as integer)                  as expected_amount_cents,
        t.amount_cents - cast(round(f.fare_cents * c.fare_multiplier) as integer)
            as amount_diff_cents

    from flagged_dup as t
    left join vehicles as v on t.vehicle_id = v.vehicle_id
    left join categories as c on v.category = c.category
    left join plazas as p on t.plaza_id = p.plaza_id
    left join fares as f
        on
            t.plaza_id = f.plaza_id
            and t.event_date between f.valid_from and f.valid_to
)

select * from enriched
