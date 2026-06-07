provider "databricks" {
  host  = var.databricks_host
  token = var.databricks_token
}

# Unity Catalog de produção — o `prod` do dbt (profiles.yml) aponta para cá.
resource "databricks_catalog" "toll" {
  name    = var.catalog_name
  comment = "Produção do toll-analytics (Unity Catalog + Delta)."
}

# Camada de ingestão (dlt / Auto Loader / COPY INTO) — equivalente ao `landing` do DuckDB.
resource "databricks_schema" "landing" {
  catalog_name = databricks_catalog.toll.name
  name         = "landing"
  comment      = "Bronze: tabelas de ingestão (substitui os seeds em prod)."
}

# Camada gold consumível (marts) — onde o BI e o dbt-toll-exec (mesh) leem.
resource "databricks_schema" "analytics" {
  catalog_name = databricks_catalog.toll.name
  name         = "analytics"
  comment      = "Gold: marts consumidos por BI e por projetos downstream (mesh)."
}

# SQL Warehouse que o dbt usa como compute em produção (http_path no profiles prod).
resource "databricks_sql_endpoint" "dbt" {
  name             = var.warehouse_name
  cluster_size     = "2X-Small"
  max_num_clusters = 1
  auto_stop_mins   = 10
}

output "warehouse_http_path" {
  description = "Use no DBX_HTTP_PATH do profiles.yml (target prod)."
  value       = databricks_sql_endpoint.dbt.odbc_params[0].path
}
