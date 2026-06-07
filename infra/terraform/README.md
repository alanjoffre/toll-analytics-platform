# infra/terraform — IaC do warehouse de produção (Databricks)

Provisiona, como **código**, o ambiente `prod` que o dbt usa (Unity Catalog + Delta):
catálogo, schemas (`landing` bronze / `analytics` gold) e um **SQL Warehouse** para o dbt.
Espelha o `target prod` do [`profiles.yml`](../../dbt-toll-analytics/profiles.yml) (ADR-7/24).

## Recursos ([main.tf](main.tf))
- `databricks_catalog.toll` — Unity Catalog de produção.
- `databricks_schema.landing` / `.analytics` — bronze (ingestão) e gold (marts).
- `databricks_sql_endpoint.dbt` — compute do dbt (output: `warehouse_http_path` → `DBX_HTTP_PATH`).

## Validar (sem nuvem) — é o que o CI faz (`terraform_ci.yml`)
```bash
terraform init -backend=false
terraform validate     # checa HCL + schema do provider, sem conectar/aplicar
```

## Aplicar (produção — precisa de credenciais)
```bash
export TF_VAR_databricks_host="https://adb-xxxx.cloud.databricks.com"
export TF_VAR_databricks_token="***"   # PAT; nunca commitar
terraform init && terraform plan && terraform apply
```

> O `apply` exige um workspace Databricks real. O CI valida a **configuração** (HCL +
> schema), não aplica — coerente com a regra de não criar recurso de nuvem sem aprovação.
