{#
  log_run_results — OBSERVABILIDADE de pipeline. Chamada no on-run-end (ver
  dbt_project.yml). Ao fim de cada execução, grava 1 linha por nó (model/seed/
  snapshot/test) numa tabela persistente `_audit_runs`, para monitorar status,
  tempo de execução e linhas afetadas ao longo do tempo.

  Robusto: só roda em tempo de execução (execute) e quando há resultados —
  assim não quebra em `dbt parse`, `dbt deps`, etc.
#}
{% macro log_run_results() %}

    {% if not execute %}
        {% do return('') %}
    {% endif %}

    {% if results is not defined or results | length == 0 %}
        {% do return('') %}
    {% endif %}

    {% set schema_name = target.schema %}

    {% set ddl %}
        create schema if not exists {{ schema_name }};
        create table if not exists {{ schema_name }}._audit_runs (
            invocation_id   varchar,
            generated_at    timestamp,
            node_id         varchar,
            resource_type   varchar,
            status          varchar,
            execution_time  double,
            rows_affected   bigint
        );
    {% endset %}
    {% do run_query(ddl) %}

    {% for res in results %}
        {% set node = res.node %}
        {% set exec_time = res.execution_time if res.execution_time is not none else 'null' %}
        {% set rows_affected = 'null' %}
        {% if res.adapter_response is mapping and res.adapter_response.get('rows_affected') is not none %}
            {% set rows_affected = res.adapter_response.get('rows_affected') %}
        {% endif %}
        {% set insert_row %}
            insert into {{ schema_name }}._audit_runs values (
                '{{ invocation_id }}',
                cast(now() as timestamp),
                '{{ node.unique_id }}',
                '{{ node.resource_type }}',
                '{{ res.status }}',
                {{ exec_time }},
                {{ rows_affected }}
            );
        {% endset %}
        {% do run_query(insert_row) %}
    {% endfor %}

    {% do log("[log_run_results] " ~ (results | length) ~ " nós gravados em " ~ schema_name ~ "._audit_runs", info=true) %}

{% endmacro %}
