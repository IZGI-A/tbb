"""Airflow DAG for TBB Bank Info ETL pipeline.

Scrapes bank list, branches, and ATMs from tbb.org.tr and loads
into PostgreSQL tables (bank_info, branch_info, atm_info).

Schedule: Monthly (1st of month, 06:00 UTC)
Chain: scrape_banks → transform → load_postgres
"""

import json
import os
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

STAGING_DIR = "/tmp/tbb_staging/bank_info"

default_args = {
    "owner": "tbb",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


def _ensure_staging_dir():
    os.makedirs(STAGING_DIR, exist_ok=True)


def scrape_banks(**context):
    from scrapers.bank_info_scraper import BankInfoScraper

    _ensure_staging_dir()

    with BankInfoScraper() as scraper:
        raw_data = scraper.scrape_all()

    staging_path = os.path.join(STAGING_DIR, f"raw_{context['ds_nodash']}.json")
    with open(staging_path, "w") as f:
        json.dump(raw_data, f, default=str)

    context["ti"].xcom_push(key="staging_path", value=staging_path)
    logger.info("Wrote bank data to %s", staging_path)


def transform(**context):
    from etl.transformers import transform_bank_info

    staging_path = context["ti"].xcom_pull(task_ids="scrape_banks", key="staging_path")
    if not staging_path:
        staging_path = os.path.join(STAGING_DIR, f"raw_{context['ds_nodash']}.json")
        logger.info("XCom miss — falling back to %s", staging_path)
    with open(staging_path) as f:
        raw_data = json.load(f)

    transformed = transform_bank_info(raw_data)

    output_path = os.path.join(STAGING_DIR, f"transformed_{context['ds_nodash']}.json")
    with open(output_path, "w") as f:
        json.dump(transformed, f, default=str)

    context["ti"].xcom_push(key="transformed_path", value=output_path)
    logger.info("Transformed bank data")


def load_postgres(**context):
    from etl.postgres_loader import load_all_bank_data

    transformed_path = context["ti"].xcom_pull(task_ids="transform", key="transformed_path")
    if not transformed_path:
        transformed_path = os.path.join(STAGING_DIR, f"transformed_{context['ds_nodash']}.json")
        logger.info("XCom miss — falling back to %s", transformed_path)
    with open(transformed_path) as f:
        data = json.load(f)

    counts = load_all_bank_data(data)
    logger.info("Loaded bank data into PostgreSQL: %s", counts)


with DAG(
    dag_id="tbb_bank_info",
    default_args=default_args,
    description="TBB Bank Info ETL Pipeline (tbb.org.tr)",
    schedule_interval="0 6 1 * *",  # 1st of month, 06:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["tbb", "bank_info"],
) as dag:

    t_scrape = PythonOperator(
        task_id="scrape_banks",
        python_callable=scrape_banks,
    )

    t_transform = PythonOperator(
        task_id="transform",
        python_callable=transform,
    )

    t_load = PythonOperator(
        task_id="load_postgres",
        python_callable=load_postgres,
    )

    t_scrape >> t_transform >> t_load
