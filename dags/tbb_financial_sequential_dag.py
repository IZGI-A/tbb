"""Orchestrator DAG: runs tbb_financial_solo for each period sequentially.

Memory-safe: processes one period at a time.
Full ETL pipeline (scrape -> transform -> load) completes for each period
before the next one begins.

Period keys are read from dags/config/financial_periods.json.

Kullanim:
  1. dags/config/financial_periods.json dosyasina cekilecek donemlerin
     key'lerini siraya koy (ilk eleman ilk cekilecek donem)
  2. Bu DAG'i tetikle:
     airflow dags trigger tbb_financial_solo_sequential

  Her donem icin tbb_financial_solo DAG'i tetiklenir, tum task'lari
  (scrape -> transform -> load) tamamlandiktan sonra siradaki doneme gecer.
"""

import json
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

PERIODS_CONFIG = os.path.join(
    os.path.dirname(__file__), "config", "financial_periods.json"
)


def _load_period_keys() -> list[int]:
    """Read period_keys from config file."""
    try:
        with open(PERIODS_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("period_keys", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


default_args = {
    "owner": "tbb",
    "retries": 0,
}

with DAG(
    dag_id="tbb_financial_solo_sequential",
    default_args=default_args,
    description=(
        "Her donemi tek tek ceker: tbb_financial_solo'yu sirayla tetikler"
    ),
    schedule_interval=None,  # sadece manuel tetikleme
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["tbb", "financial", "solo", "sequential"],
) as dag:
    period_keys = _load_period_keys()

    prev_task = None
    for idx, key in enumerate(period_keys):
        trigger = TriggerDagRunOperator(
            task_id=f"period_{idx}",
            trigger_dag_id="tbb_financial_solo",
            conf={"period_keys": [key]},
            wait_for_completion=True,
            poke_interval=60,  # her 60 saniyede tamamlandi mi kontrol et
            allowed_states=["success"],
            failed_states=["failed"],
        )
        if prev_task:
            prev_task >> trigger
        prev_task = trigger
