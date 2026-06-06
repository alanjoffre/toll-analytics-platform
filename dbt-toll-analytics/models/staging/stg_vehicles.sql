with source as (
    select * from {{ source('toll_raw', 'raw_vehicles') }}
)

select
    cast(vehicle_id as varchar)    as vehicle_id,
    -- LGPD: mascara a placa (mantém os 3 primeiros caracteres)
    left(trim(plate), 3) || '****' as plate_masked,
    cast(category as integer)      as category,
    cast(account_id as varchar)    as account_id
from source
