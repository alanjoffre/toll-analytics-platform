-- Teste SINGULAR (1 arquivo = 1 asserção específica): redundância proposital
-- garantindo que o fato não tem transaction_id duplicado após o dedup + incremental.
-- Retorna linhas que violam (count > 1); vazio = passou.

select
    transaction_id,
    count(*) as n
from {{ ref('fct_toll_transactions') }}
group by transaction_id
having count(*) > 1
