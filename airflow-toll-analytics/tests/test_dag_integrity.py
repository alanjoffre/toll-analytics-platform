"""Teste de INTEGRIDADE dos DAGs (DAG integrity test).

Carrega todos os DAGs via DagBag e garante:
- nenhum erro de import (sintaxe, dependências, caminhos);
- DAGs esperados existem;
- nenhum ciclo e default_args mínimos presentes.

Roda no CI sem precisar de scheduler/banco — é o smoke test padrão de Airflow.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from airflow.models import DagBag

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PYTHONPATH", str(PROJECT_ROOT))


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(PROJECT_ROOT / "dags"), include_examples=False)


def test_no_import_errors(dagbag: DagBag) -> None:
    assert not dagbag.import_errors, f"Erros de import: {dagbag.import_errors}"


def test_expected_dags_present(dagbag: DagBag) -> None:
    for dag_id in (
        "toll_analytics_pipeline",
        "toll_analytics_observability",
        "toll_analytics_quality_gate",
        "toll_analytics_backfill",
    ):
        assert dag_id in dagbag.dags, f"DAG ausente: {dag_id}"


def test_dags_have_retries_and_tags(dagbag: DagBag) -> None:
    for dag_id, dag in dagbag.dags.items():
        assert dag.default_args.get("retries", 0) >= 1, f"{dag_id} sem retries"
        assert dag.tags, f"{dag_id} sem tags"
