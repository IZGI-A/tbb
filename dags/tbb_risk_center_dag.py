"""Airflow DAG for TBB Risk Center ETL pipeline.

Schedule: Monthly (1st of month, 06:00 UTC)
Chain: scrape_data → transform → load_clickhouse
"""

import json
import os
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

STAGING_DIR = "/tmp/tbb_staging/risk_center"

default_args = {
    "owner": "tbb",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


def _ensure_staging_dir():
    os.makedirs(STAGING_DIR, exist_ok=True)


def scrape_data(**context):
    from scrapers.risk_center_scraper import RiskCenterScraper

    _ensure_staging_dir()

    with RiskCenterScraper() as scraper:
        raw_data = scraper.scrape_all()

    staging_path = os.path.join(STAGING_DIR, f"raw_{context['ds_nodash']}.json")
    with open(staging_path, "w") as f:
        json.dump(raw_data, f, default=str)

    context["ti"].xcom_push(key="staging_path", value=staging_path)
    logger.info("Wrote %d records to %s", len(raw_data), staging_path)


def transform(**context):
    from etl.transformers import transform_risk_center

    staging_path = context["ti"].xcom_pull(task_ids="scrape_data", key="staging_path")
    if not staging_path:
        staging_path = os.path.join(STAGING_DIR, f"raw_{context['ds_nodash']}.json")
        logger.info("XCom miss — falling back to %s", staging_path)
    with open(staging_path) as f:
        raw_data = json.load(f)

    transformed = transform_risk_center(raw_data)

    output_path = os.path.join(STAGING_DIR, f"transformed_{context['ds_nodash']}.json")
    with open(output_path, "w") as f:
        json.dump(transformed, f, default=str)

    context["ti"].xcom_push(key="transformed_path", value=output_path)
    logger.info("Transformed %d records", len(transformed))


def load_clickhouse(**context):
    from etl.clickhouse_loader import load_risk_center

    transformed_path = context["ti"].xcom_pull(task_ids="transform", key="transformed_path")
    if not transformed_path:
        transformed_path = os.path.join(STAGING_DIR, f"transformed_{context['ds_nodash']}.json")
        logger.info("XCom miss — falling back to %s", transformed_path)
    with open(transformed_path) as f:
        rows = json.load(f)

    count = load_risk_center(rows)
    logger.info("Loaded %d rows into ClickHouse", count)


with DAG(
    dag_id="tbb_risk_center",
    default_args=default_args,
    description="TBB Risk Center ETL Pipeline (Selenium Scraper)",
    schedule_interval="0 6 1 * *",  # 1st of month, 06:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["tbb", "risk_center"],
) as dag:

    t_scrape = PythonOperator(
        task_id="scrape_data",
        python_callable=scrape_data,
    )

    t_transform = PythonOperator(
        task_id="transform",
        python_callable=transform,
    )

    t_load = PythonOperator(
        task_id="load_clickhouse",
        python_callable=load_clickhouse,
    )

    t_scrape >> t_transform >> t_load
