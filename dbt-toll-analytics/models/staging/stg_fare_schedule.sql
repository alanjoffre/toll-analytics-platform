with source as (
    select * from {{ source('toll_raw', 'raw_fare_schedule') }}
)

select
    cast(plaza_id as varchar)   as plaza_id,
    cast(fare_cents as integer) as fare_cents,
    cast(valid_from as date)    as valid_from,
    cast(valid_to as date)      as valid_to
from source
