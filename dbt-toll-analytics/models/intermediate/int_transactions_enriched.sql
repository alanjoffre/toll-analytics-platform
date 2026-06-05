-- Duplicidade vem do model EPHEMERAL int_duplicate_flags (inlinado como CTE):
-- separa "achar duplicata" de "enriquecer". Aqui fazemos os joins + a tarifa
-- point-in-time + a diferença esperada.
with flagged_dup as (
    select * from {{ ref('int_duplicate_flags') }}
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

        -- TARIFA POINT-IN-TIME: a tarifa vigente NA DATA do evento. Evita falso
        -- positivo de "tarifa divergente" em transações históricas (ver §7 do PLANO).
        -- LEFT JOIN: sem schedule -> sem esperado -> não acusa divergência.
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
