{#
  cents_to_brl — converte um valor em CENTAVOS para REAIS (numérico, 2 casas).
  Centralizar isto numa macro evita "/100" espalhado e mágico pelo projeto.
  Uso: {{ cents_to_brl('amount_cents') }}  ->  round(amount_cents / 100.0, 2)
#}
{% macro cents_to_brl(cents_column) %}
    round(cast({{ cents_column }} as double) / 100.0, 2)
{% endmacro %}
