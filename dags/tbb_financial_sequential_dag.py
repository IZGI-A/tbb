"""Orchestrator DAGs: runs financial DAGs for each period sequentially.

Memory-safe: processes one period at a time.
Full ETL pipeline (scrape -> transform -> load) completes for each period
before the next one begins.

Two sequential DAGs:
  1. tbb_financial_solo_sequential        — TFRS9-SOLO (2018+)
  2. tbb_financial_solo_legacy_sequential  — SOLO (2002-2017)

Kullanim:
  1. Config dosyasina cekilecek donemlerin key'lerini siraya koy
     - TFRS9:  dags/config/financial_periods.json
     - Legacy: dags/config/financial_periods_legacy.json
  2. DAG'i tetikle:
     airflow dags trigger tbb_financial_solo_sequential
     airflow dags trigger tbb_financial_solo_legacy_sequential
"""

import json
import os
from datetime import datetime

from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")


def _load_period_keys(config_file: str = "financial_periods.json") -> list[int]:
    """Read period_keys from config file."""
    try:
        with open(os.path.join(CONFIG_DIR, config_file), encoding="utf-8") as f:
            data = json.load(f)
        return data.get("period_keys", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _build_sequential_dag(
    dag_id: str,
    trigger_dag_id: str,
    config_file: str,
    description: str,
    tags: list[str],
):
    """Create a sequential DAG that triggers another DAG per period."""
    default_args = {
        "owner": "tbb",
        "retries": 0,
    }

    with DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=description,
        schedule_interval=None,
        start_date=datetime(2024, 1, 1),
        catchup=False,
        tags=tags,
    ) as dag:
        period_keys = _load_period_keys(config_file)

        prev_task = None
        for idx, key in enumerate(period_keys):
            trigger = TriggerDagRunOperator(
                task_id=f"period_{idx}",
                trigger_dag_id=trigger_dag_id,
                conf={"period_keys": [key]},
                wait_for_completion=True,
                poke_interval=60,
                allowed_states=["success"],
                failed_states=["failed"],
            )
            if prev_task:
                prev_task >> trigger
            prev_task = trigger

    return dag


# ── Sequential DAG 1: TFRS9-SOLO (2018+) ──────────────────────
dag_solo_seq = _build_sequential_dag(
    dag_id="tbb_financial_solo_sequential",
    trigger_dag_id="tbb_financial_solo",
    config_file="financial_periods.json",
    description="Her donemi tek tek ceker: tbb_financial_solo'yu sirayla tetikler",
    tags=["tbb", "financial", "solo", "sequential"],
)

# ── Sequential DAG 2: SOLO Legacy (2002-2017) ─────────────────
dag_legacy_seq = _build_sequential_dag(
    dag_id="tbb_financial_solo_legacy_sequential",
    trigger_dag_id="tbb_financial_solo_legacy",
    config_file="financial_periods_legacy.json",
    description="Her donemi tek tek ceker: tbb_financial_solo_legacy'yi sirayla tetikler",
    tags=["tbb", "financial", "solo", "legacy", "sequential"],
)
