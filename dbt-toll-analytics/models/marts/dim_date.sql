-- dim_date — dimensão de calendário gerada com dbt_utils.date_spine.
-- ROBUSTEZ: a faixa NÃO é fixa em 2026; é derivada do min/max real das transações
-- (anos-calendário completos, com folga). Assim, qualquer transação fora de 2026
-- continua tendo date_key correspondente e o relationships do fato não quebra.

{% set bounds_query %}
    select
        min(event_date) as min_d,
        max(event_date) as max_d
    from {{ ref('stg_toll_transactions') }}
{% endset %}

{% if execute %}
    {% set res = run_query(bounds_query) %}
    {% set min_year = (res.columns[0].values()[0] | string)[0:4] | int %}
    {% set max_year = (res.columns[1].values()[0] | string)[0:4] | int %}
{% else %}
    {# fallback para parse/compile sem banco #}
    {% set min_year = 2026 %}
    {% set max_year = 2026 %}
{% endif %}

{% set start_expr = "cast('" ~ min_year ~ "-01-01' as date)" %}
{% set end_expr   = "cast('" ~ (max_year + 1) ~ "-01-01' as date)" %}

with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date=start_expr,
        end_date=end_expr
    ) }}
)

select
    cast(strftime(date_day, '%Y%m%d') as integer)           as date_key,
    cast(date_day as date)                                  as date_day,
    cast(extract('year' from date_day) as integer)          as year,
    cast(extract('month' from date_day) as integer)         as month,
    cast(extract('day' from date_day) as integer)           as day,
    cast(extract('dow' from date_day) as integer)           as day_of_week,
    cast(strftime(date_day, '%A') as varchar)               as day_name,
    cast(extract('dow' from date_day) in (0, 6) as boolean) as is_weekend
from spine
