"""Airflow DAG for TBB Financial Statements ETL pipeline.

Schedule: Weekly (Monday 06:00 UTC)
Chain: scrape_solo → transform_solo → load_solo → scrape_consolidated → transform_consolidated → load_consolidated

Solo and consolidated are scraped sequentially to avoid Chrome tab crashes
from excessive memory usage.
"""

import json
import os
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

STAGING_DIR = "/tmp/tbb_staging/financial"

default_args = {
    "owner": "tbb",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


def _ensure_staging_dir():
    os.makedirs(STAGING_DIR, exist_ok=True)


def _scrape_table(table_key: str, **context):
    from scrapers.financial_scraper import FinancialScraper

    _ensure_staging_dir()

    with FinancialScraper() as scraper:
        raw_data = scraper.scrape_all(table_keys=[table_key])

    staging_path = os.path.join(
        STAGING_DIR, f"raw_{table_key}_{context['ds_nodash']}.json"
    )
    with open(staging_path, "w") as f:
        json.dump(raw_data, f, default=str)

    context["ti"].xcom_push(key=f"staging_path_{table_key}", value=staging_path)
    logger.info("Wrote %d %s records to %s", len(raw_data), table_key, staging_path)


def _transform_table(table_key: str, **context):
    from etl.transformers import transform_financial

    staging_path = context["ti"].xcom_pull(
        task_ids=f"scrape_{table_key}", key=f"staging_path_{table_key}"
    )
    if not staging_path:
        staging_path = os.path.join(
            STAGING_DIR, f"raw_{table_key}_{context['ds_nodash']}.json"
        )
        logger.info("XCom miss — falling back to %s", staging_path)
    with open(staging_path) as f:
        raw_data = json.load(f)

    transformed = transform_financial(raw_data)

    output_path = os.path.join(
        STAGING_DIR, f"transformed_{table_key}_{context['ds_nodash']}.json"
    )
    with open(output_path, "w") as f:
        json.dump(transformed, f, default=str)

    context["ti"].xcom_push(key=f"transformed_path_{table_key}", value=output_path)
    logger.info("Transformed %d %s records", len(transformed), table_key)


def _load_table(table_key: str, **context):
    from etl.clickhouse_loader import load_financial_statements

    transformed_path = context["ti"].xcom_pull(
        task_ids=f"transform_{table_key}", key=f"transformed_path_{table_key}"
    )
    if not transformed_path:
        transformed_path = os.path.join(
            STAGING_DIR, f"transformed_{table_key}_{context['ds_nodash']}.json"
        )
        logger.info("XCom miss — falling back to %s", transformed_path)
    with open(transformed_path) as f:
        rows = json.load(f)

    count = load_financial_statements(rows)
    logger.info("Loaded %d %s rows into ClickHouse", count, table_key)


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


with DAG(
    dag_id="tbb_financial_statements",
    default_args=default_args,
    description="TBB Financial Statements ETL Pipeline (Solo + Consolidated)",
    schedule_interval="0 6 * * 1",  # Monday 06:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["tbb", "financial"],
) as dag:

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

    # Sequential: solo pipeline → consolidated pipeline
    t_scrape_solo >> t_transform_solo >> t_load_solo >> t_scrape_cons >> t_transform_cons >> t_load_cons
