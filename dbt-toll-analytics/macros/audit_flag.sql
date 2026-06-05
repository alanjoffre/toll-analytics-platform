{#
  audit_flag — REGRA DE NEGÓCIO da auditoria, isolada numa macro p/ ser testável
  (ver models/marts/_unit_tests.yml). Recebe nomes de colunas e devolve uma
  expressão CASE que classifica a transação em UMA flag, por ordem de prioridade:

    1. VALOR_INVALIDO      -> valor nulo ou <= 0 (nem dá p/ avaliar tarifa)
    2. COBRANCA_EM_FALHA   -> status FAILED/REVERSED mas com valor cobrado (> 0)
    3. TARIFA_DIVERGENTE   -> valor cobrado != valor esperado (point-in-time)
    4. POSSIVEL_DUPLICIDADE-> mesma passagem repetida na janela de N segundos
    5. OK                  -> nada a sinalizar

  Em auditoria a regra é FLAG, não DELETE: nada é removido, tudo é classificado.
#}
{% macro audit_flag(status_col, amount_col, expected_col, is_duplicate_col) %}
    case
        when {{ amount_col }} is null or {{ amount_col }} <= 0
            then 'VALOR_INVALIDO'
        when {{ status_col }} in ('FAILED', 'REVERSED') and {{ amount_col }} > 0
            then 'COBRANCA_EM_FALHA'
        when {{ expected_col }} is not null and {{ amount_col }} <> {{ expected_col }}
            then 'TARIFA_DIVERGENTE'
        when {{ is_duplicate_col }}
            then 'POSSIVEL_DUPLICIDADE'
        else 'OK'
    end
{% endmacro %}
