# Makefile — rotinas do projeto dbt-toll-analytics.
# Uso: make <alvo>   (ex.: make build, make check-docs)
# Assume o virtualenv em .venv (criado em "Como rodar" no README).

VENV     := .venv
PY       := $(VENV)/bin/python
DBT      := $(VENV)/bin/dbt
SQLFLUFF := $(VENV)/bin/sqlfluff

.PHONY: help build docs check-docs lint test observability freshness deps all

help:
	@echo "Alvos disponíveis:"
	@echo "  make deps          - dbt deps (instala packages)"
	@echo "  make build         - dbt build (CI de PR) + REGENERA a documentação se passar"
	@echo "  make docs          - regenera só o documento Word"
	@echo "  make check-docs    - verifica se a documentação está em dia com o código"
	@echo "  make lint          - SQLFluff (models, tests, snapshots, macros)"
	@echo "  make observability - testes de anomalia (tag:observability)"
	@echo "  make freshness     - dbt source freshness (contrato de ingestão)"
	@echo "  make all           - lint + build + check-docs"

deps:
	$(DBT) deps --profiles-dir .

# Build do CI de PR (exclui observability) E, SÓ SE passar (&&), regenera a doc.
# Em seguida confere o drift — assim a documentação nunca fica atrás do código.
build:
	$(DBT) build --exclude tag:observability --profiles-dir . && $(MAKE) docs && $(MAKE) check-docs

docs:
	$(PY) docs/gerar_documentacao.py

check-docs:
	$(PY) docs/check_docs_sync.py

lint:
	$(SQLFLUFF) lint models tests snapshots macros --dialect duckdb

observability:
	$(DBT) test --select tag:observability --profiles-dir .

freshness:
	$(DBT) source freshness --profiles-dir .

all: lint build
