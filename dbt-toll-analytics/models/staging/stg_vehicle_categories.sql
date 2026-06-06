with source as (
    select * from {{ source('toll_raw', 'raw_vehicle_categories') }}
)

select
    cast(category as integer)       as category,
    trim(description)               as description,
    cast(fare_multiplier as double) as fare_multiplier
from source
