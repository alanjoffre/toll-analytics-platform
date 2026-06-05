{% docs audit_flag_values %}
Classificação da auditoria, por ordem de prioridade:

- **VALOR_INVALIDO** — valor nulo ou ≤ 0 (nem dá para avaliar tarifa).
- **COBRANCA_EM_FALHA** — status `FAILED`/`REVERSED` mas com valor cobrado (> 0).
- **TARIFA_DIVERGENTE** — valor cobrado ≠ tarifa esperada (point-in-time).
- **POSSIVEL_DUPLICIDADE** — mesma passagem na janela de N segundos.
- **OK** — nada a sinalizar (não aparece no produto de auditoria).
{% enddocs %}

{% docs col_amount_cents %}
Valor cobrado, em **centavos inteiros** (exato). A conversão para BRL acontece só
na exibição (`cents_to_brl`), nunca somando reais arredondados — ver ADR-15.
{% enddocs %}
