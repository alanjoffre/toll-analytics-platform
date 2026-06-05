with plazas as (
    select * from {{ ref('stg_toll_plazas') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['plaza_id']) }} as plaza_sk,
    plaza_id,
    plaza_name,
    highway,
    uf
from plazas
