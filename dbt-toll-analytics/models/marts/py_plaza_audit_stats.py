"""GOLD — Python model: estatística de auditoria por praça.

Demonstra um PYTHON MODEL do dbt (dbt-duckdb): o dbt orquestra/versiona/testa
igual a um model SQL, mas a lógica roda em Python. Aqui faz sentido porque é
ESTATÍSTICA entre praças (z-score) — natural em pandas, verboso em SQL.

Entrega, por praça: total, suspeitas, taxa de suspeita, vazamento (centavos) e o
z-score da taxa de suspeita entre as praças (quão fora da média a praça está).
"""


def model(dbt, session):
    dbt.config(materialized="table")

    # ref() para o fato — retorna relação DuckDB; .df() converte para pandas
    fct = dbt.ref("fct_toll_transactions").df()

    grouped = (
        fct.groupby("plaza_id")
        .agg(
            total_transactions=("transaction_id", "count"),
            suspect_transactions=("audit_flag", lambda s: int((s != "OK").sum())),
            leakage_cents=("amount_diff_cents", lambda s: int(-s[s < 0].sum())),
        )
        .reset_index()
    )

    grouped["suspect_rate"] = (
        grouped["suspect_transactions"] / grouped["total_transactions"]
    ).round(4)

    # z-score da taxa de suspeita ENTRE praças (estatística — natural em Python)
    mu = grouped["suspect_rate"].mean()
    sigma = grouped["suspect_rate"].std(ddof=0)
    grouped["suspect_rate_zscore"] = (
        ((grouped["suspect_rate"] - mu) / sigma).round(3) if sigma else 0.0
    )

    return grouped
