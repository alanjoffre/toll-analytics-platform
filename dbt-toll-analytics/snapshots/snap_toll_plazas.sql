{% snapshot snap_toll_plazas %}

{{
    config(
        unique_key='plaza_id',
        strategy='check',
        check_cols=['plaza_name', 'highway', 'uf'],
        invalidate_hard_deletes=True
    )
}}

-- SCD2 nativo do dbt: a cada `dbt snapshot`, se algum atributo da praça mudar,
-- o dbt fecha a versão anterior (dbt_valid_to) e abre uma nova.
-- Decisão de design (ADR-2): para a TARIFA, que precisa de história determinística
-- já na 1ª execução, usamos a seed `raw_fare_schedule` em vez de snapshot.
    select
        plaza_id,
        plaza_name,
        highway,
        uf
    from {{ ref('stg_toll_plazas') }}

{% endsnapshot %}
