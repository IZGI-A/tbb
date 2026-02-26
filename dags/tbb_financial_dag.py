"""Airflow DAGs for TBB Financial Statements ETL pipeline.

Three independent DAGs:
  - tbb_financial_solo:         TFRS9-SOLO statements (2018+)
  - tbb_financial_consolidated: TFRS9-KONSOLIDE statements (2018+)
  - tbb_financial_solo_legacy:  SOLO statements (2002-2017, pre-TFRS9)

Schedule: Weekly (Monday 06:00 UTC)
Chain (each DAG): scrape → transform → load

Period selection (oncelik sirasi):
  1. --conf ile verilen period_keys (en yuksek oncelik)
  2. dags/config/financial_periods.json dosyasindaki period_keys
  3. Bos liste = sadece en son donem (site varsayilani)

Ornekler:
  # --conf ile belirli donemler
  airflow dags trigger tbb_financial_solo --conf '{"period_keys": [139, 138, 137]}'

  # config dosyasindan (dags/config/financial_periods.json duzenle)
  airflow dags trigger tbb_financial_solo
"""

import json
import os
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

STAGING_DIR = "/tmp/tbb_staging/financial"
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")

# Per-table-key config file mapping
_PERIODS_CONFIG_MAP = {
    "solo": "financial_periods.json",
    "consolidated": "financial_periods.json",
    "solo_legacy": "financial_periods_legacy.json",
    "consolidated_legacy": "financial_periods_legacy.json",
}

default_args = {
    "owner": "tbb",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=4),
}


def _ensure_staging_dir():
    os.makedirs(STAGING_DIR, exist_ok=True)


def _load_period_keys_from_config(table_key: str = "solo") -> list[int]:
    """Read period_keys from the config file for the given table_key."""
    config_file = _PERIODS_CONFIG_MAP.get(table_key, "financial_periods.json")
    config_path = os.path.join(CONFIG_DIR, config_file)
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("period_keys", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _resolve_period_keys(context, table_key: str = "solo") -> list[int] | None:
    """Determine which period keys to use.

    Priority:
      1. --conf '{"period_keys": [...]}' (highest)
      2. Config file for the table_key
      3. Empty → None (site default = most recent period)
    """
    # 1. From --conf (DAG params)
    keys = context["params"].get("period_keys")
    if keys:
        logger.info("Period keys from --conf: %s", keys)
        return keys

    # 2. From config file
    keys = _load_period_keys_from_config(table_key)
    if keys:
        logger.info("Period keys from config file (%s): %s", table_key, keys)
        return keys

    # 3. Default
    logger.info("No period keys specified — using site default (most recent)")
    return None


def _scrape_table(table_key: str, **context):
    from scrapers.financial_scraper import FinancialScraper

    _ensure_staging_dir()

    period_keys = _resolve_period_keys(context, table_key=table_key)

    with FinancialScraper() as scraper:
        raw_data = scraper.scrape_all(
            table_keys=[table_key], period_keys=period_keys,
        )

    # Write as JSONL (one JSON object per line) to enable streaming reads
    staging_path = os.path.join(
        STAGING_DIR, f"raw_{table_key}_{context['ds_nodash']}.jsonl"
    )
    with open(staging_path, "w", encoding="utf-8") as f:
        for record in raw_data:
            f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")

    context["ti"].xcom_push(key=f"staging_path_{table_key}", value=staging_path)
    logger.info("Wrote %d %s records to %s", len(raw_data), table_key, staging_path)


def _transform_table(table_key: str, **context):
    from etl.transformers import transform_financial

    staging_path = context["ti"].xcom_pull(
        task_ids=f"scrape_{table_key}", key=f"staging_path_{table_key}"
    )
    if not staging_path:
        # Try JSONL first, fall back to old JSON format
        staging_path = os.path.join(
            STAGING_DIR, f"raw_{table_key}_{context['ds_nodash']}.jsonl"
        )
        if not os.path.exists(staging_path):
            staging_path = os.path.join(
                STAGING_DIR, f"raw_{table_key}_{context['ds_nodash']}.json"
            )
        logger.info("XCom miss — falling back to %s", staging_path)

    output_path = os.path.join(
        STAGING_DIR, f"transformed_{table_key}_{context['ds_nodash']}.jsonl"
    )

    # Stream processing: read line by line, transform in batches, write
    BATCH_SIZE = 50000
    total = 0
    batch = []

    with open(output_path, "w", encoding="utf-8") as out_f:
        if staging_path.endswith(".jsonl"):
            # JSONL format: one record per line
            with open(staging_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    batch.append(json.loads(line))
                    if len(batch) >= BATCH_SIZE:
                        transformed = transform_financial(batch)
                        for row in transformed:
                            out_f.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
                        total += len(transformed)
                        batch = []
        else:
            # Legacy JSON array format
            with open(staging_path, encoding="utf-8") as f:
                batch = json.load(f)

        if batch:
            transformed = transform_financial(batch)
            for row in transformed:
                out_f.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
            total += len(transformed)

    context["ti"].xcom_push(key=f"transformed_path_{table_key}", value=output_path)
    logger.info("Transformed %d %s records", total, table_key)


def _load_table(table_key: str, **context):
    from etl.clickhouse_loader import load_financial_statements

    transformed_path = context["ti"].xcom_pull(
        task_ids=f"transform_{table_key}", key=f"transformed_path_{table_key}"
    )
    if not transformed_path:
        transformed_path = os.path.join(
            STAGING_DIR, f"transformed_{table_key}_{context['ds_nodash']}.jsonl"
        )
        if not os.path.exists(transformed_path):
            transformed_path = os.path.join(
                STAGING_DIR, f"transformed_{table_key}_{context['ds_nodash']}.json"
            )
        logger.info("XCom miss — falling back to %s", transformed_path)

    # Stream load: read in batches to avoid OOM
    BATCH_SIZE = 50000
    total = 0

    if transformed_path.endswith(".jsonl"):
        batch = []
        with open(transformed_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                batch.append(json.loads(line))
                if len(batch) >= BATCH_SIZE:
                    total += load_financial_statements(batch)
                    batch = []
        if batch:
            total += load_financial_statements(batch)
    else:
        # Legacy JSON array format
        with open(transformed_path, encoding="utf-8") as f:
            rows = json.load(f)
        total = load_financial_statements(rows)

    logger.info("Loaded %d %s rows into ClickHouse", total, table_key)


# --- DAG params shared by both DAGs ---

dag_params = {
    "period_keys": Param(
        default=[],
        type="array",
        description=(
            "Period ID keys to scrape. Leave empty for the most recent "
            "period (site default). Use FinancialScraper._get_available_periods() "
            "to discover valid keys."
        ),
    ),
}


# --- Task factory functions (closures for PythonOperator) ---

def scrape_solo(**ctx):
    _scrape_table("solo", **ctx)

def transform_solo(**ctx):
    _transform_table("solo", **ctx)

def load_solo(**ctx):
    _load_table("solo", **ctx)

def scrape_consolidated(**ctx):
    _scrape_table("consolidated", **ctx)

def transform_consolidated(**ctx):
    _transform_table("consolidated", **ctx)

def load_consolidated(**ctx):
    _load_table("consolidated", **ctx)

def scrape_solo_legacy(**ctx):
    _scrape_table("solo_legacy", **ctx)

def transform_solo_legacy(**ctx):
    _transform_table("solo_legacy", **ctx)

def load_solo_legacy(**ctx):
    _load_table("solo_legacy", **ctx)


# ── DAG 1: Solo ─────────────────────────────────────────────────

with DAG(
    dag_id="tbb_financial_solo",
    default_args=default_args,
    description="TBB Financial Statements ETL Pipeline (Solo)",
    schedule_interval="0 6 * * 1",  # Monday 06:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["tbb", "financial", "solo"],
    params=dag_params,
) as dag_solo:

    t_scrape_solo = PythonOperator(
        task_id="scrape_solo",
        python_callable=scrape_solo,
    )
    t_transform_solo = PythonOperator(
        task_id="transform_solo",
        python_callable=transform_solo,
    )
    t_load_solo = PythonOperator(
        task_id="load_solo",
        python_callable=load_solo,
    )

    t_scrape_solo >> t_transform_solo >> t_load_solo


# ── DAG 2: Consolidated ─────────────────────────────────────────

with DAG(
    dag_id="tbb_financial_consolidated",
    default_args=default_args,
    description="TBB Financial Statements ETL Pipeline (Consolidated)",
    schedule_interval="0 6 * * 1",  # Monday 06:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["tbb", "financial", "consolidated"],
    params=dag_params,
) as dag_consolidated:

    t_scrape_cons = PythonOperator(
        task_id="scrape_consolidated",
        python_callable=scrape_consolidated,
    )
    t_transform_cons = PythonOperator(
        task_id="transform_consolidated",
        python_callable=transform_consolidated,
    )
    t_load_cons = PythonOperator(
        task_id="load_consolidated",
        python_callable=load_consolidated,
    )

    t_scrape_cons >> t_transform_cons >> t_load_cons


# ── DAG 3: Solo Legacy (pre-2018) ─────────────────────────────

with DAG(
    dag_id="tbb_financial_solo_legacy",
    default_args=default_args,
    description="TBB Financial Statements ETL Pipeline (Solo Legacy 2002-2017)",
    schedule_interval=None,  # manual trigger only (historical data)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["tbb", "financial", "solo", "legacy"],
    params=dag_params,
) as dag_solo_legacy:

    t_scrape_legacy = PythonOperator(
        task_id="scrape_solo_legacy",
        python_callable=scrape_solo_legacy,
    )
    t_transform_legacy = PythonOperator(
        task_id="transform_solo_legacy",
        python_callable=transform_solo_legacy,
    )
    t_load_legacy = PythonOperator(
        task_id="load_solo_legacy",
        python_callable=load_solo_legacy,
    )

    t_scrape_legacy >> t_transform_legacy >> t_load_legacy
