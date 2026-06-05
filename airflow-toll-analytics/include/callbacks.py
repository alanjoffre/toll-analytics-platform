"""Callbacks de ALERTA do pipeline.

Estratégia sem dependência obrigatória de provider:
- Sempre loga um resumo claro da falha (task, dag, execução, log_url).
- Se a variável de ambiente SLACK_WEBHOOK_URL estiver definida, envia um aviso
  ao Slack via webhook (stdlib urllib — sem instalar provider).

Em produção real, troque por SlackWebhookOperator/PagerDuty/e-mail conforme o
padrão do time. O ponto aqui é demonstrar o GANCHO de observabilidade/alerta
que o Airflow entrega (on_failure_callback / sla_miss_callback).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request

log = logging.getLogger("toll_analytics.alerts")


def _format(context: dict) -> str:
    ti = context.get("task_instance")
    dag_id = getattr(getattr(ti, "dag_id", None), "__str__", lambda: "?")()
    task_id = getattr(ti, "task_id", "?")
    run_id = context.get("run_id", "?")
    exc = context.get("exception")
    log_url = getattr(ti, "log_url", "")
    return (
        f":red_circle: *Pipeline toll_analytics FALHOU*\n"
        f"• DAG: `{dag_id}`\n"
        f"• Task: `{task_id}`\n"
        f"• Run: `{run_id}`\n"
        f"• Erro: `{exc}`\n"
        f"• Log: {log_url}"
    )


def notify_failure(context: dict) -> None:
    """on_failure_callback: loga e (opcionalmente) avisa o Slack."""
    message = _format(context)
    log.error("ALERTA DE FALHA\n%s", message)

    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        log.info("SLACK_WEBHOOK_URL não definido — alerta apenas em log.")
        return
    try:
        payload = json.dumps({"text": message}).encode("utf-8")
        req = urllib.request.Request(
            webhook, data=payload, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)  # noqa: S310 (webhook controlado)
        log.info("Alerta enviado ao Slack.")
    except Exception as err:  # noqa: BLE001 — alerta nunca deve derrubar a task
        log.warning("Falha ao enviar alerta ao Slack: %s", err)


def notify_sla_miss(dag, task_list, blocking_task_list, slas, blocking_tis) -> None:
    """sla_miss_callback: pipeline atrasou além do SLA definido no DAG."""
    log.warning(
        "SLA ESTOURADO em %s — tasks atrasadas: %s",
        getattr(dag, "dag_id", "?"),
        [getattr(s, "task_id", "?") for s in (slas or [])],
    )
