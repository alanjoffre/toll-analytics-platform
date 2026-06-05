{#
  Teste GENÉRICO customizado e reutilizável: "não deveria haver valor cobrado
  (> 0) em transação com status FAILED/REVERSED". Um teste genérico retorna as
  linhas que VIOLAM a regra — se vier vazio, passa.

  Uso (em qualquer .yml):
    tests:
      - not_charged_when_failed:
          status_column: status
          amount_column: amount_cents
#}
{% test not_charged_when_failed(model, status_column, amount_column) %}

select
    {{ status_column }} as status,
    {{ amount_column }} as amount
from {{ model }}
where {{ status_column }} in ('FAILED', 'REVERSED')
  and {{ amount_column }} > 0

{% endtest %}
