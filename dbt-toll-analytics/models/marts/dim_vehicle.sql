with vehicles as (
    select * from {{ ref('stg_vehicles') }}
),

categories as (
    select * from {{ ref('stg_vehicle_categories') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['v.vehicle_id']) }} as vehicle_sk,
    v.vehicle_id,
    v.plate_masked,
    v.category,
    c.description                                            as category_description,
    c.fare_multiplier,
    v.account_id
from vehicles as v
left join categories as c on v.category = c.category
