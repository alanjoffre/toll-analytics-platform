with source as (
    select * from {{ ref('raw_toll_plazas') }}
)

select
    cast(plaza_id as varchar) as plaza_id,
    trim(plaza_name)          as plaza_name,
    upper(trim(highway))      as highway,
    upper(trim(uf))           as uf
from source
