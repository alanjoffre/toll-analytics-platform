variable "databricks_host" {
  type        = string
  description = "Workspace URL do Databricks (ex.: https://adb-xxxx.cloud.databricks.com)."
  default     = ""
}

variable "databricks_token" {
  type        = string
  description = "PAT do Databricks. Forneça via TF_VAR_databricks_token (nunca commitar)."
  sensitive   = true
  default     = ""
}

variable "catalog_name" {
  type        = string
  description = "Unity Catalog de produção do toll-analytics."
  default     = "toll_prod"
}

variable "warehouse_name" {
  type        = string
  description = "SQL Warehouse que o dbt usa em produção."
  default     = "toll-dbt-wh"
}
