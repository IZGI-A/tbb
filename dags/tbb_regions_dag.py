"""Airflow DAG for TBB Regional Statistics ETL pipeline.

Schedule: Monthly (1st of month, 06:00 UTC)
Chain: fetch_metadata → fetch_data → transform → load_clickhouse
"""

import json
import os
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

STAGING_DIR = "/tmp/tbb_staging/regions"

default_args = {
    "owner": "tbb",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


def _ensure_staging_dir():
    os.makedirs(STAGING_DIR, exist_ok=True)


def fetch_metadata(**context):
    from source.scrapers.region_scraper import RegionScraper

    _ensure_staging_dir()
    scraper = RegionScraper()

    years = scraper.fetch_years()
    year_ids = [y["ID"] for y in years if "ID" in y]
    context["ti"].xcom_push(key="year_ids", value=year_ids[-3:])  # Last 3 years
    logger.info("Pushed %d year IDs to XCom", len(year_ids[-3:]))


def fetch_data(**context):
    from source.scrapers.region_scraper import RegionScraper

    _ensure_staging_dir()
    year_ids = context["ti"].xcom_pull(task_ids="fetch_metadata", key="year_ids")

    scraper = RegionScraper()
    raw_data = scraper.scrape_all(year_ids=year_ids)

    staging_path = os.path.join(STAGING_DIR, f"raw_{context['ds_nodash']}.json")
    with open(staging_path, "w") as f:
        json.dump(raw_data, f, default=str)

    context["ti"].xcom_push(key="staging_path", value=staging_path)
    logger.info("Wrote %d records to %s", len(raw_data), staging_path)


def transform(**context):
    from source.etl.transformers import transform_regions

    staging_path = context["ti"].xcom_pull(task_ids="fetch_data", key="staging_path")
    with open(staging_path) as f:
        raw_data = json.load(f)

    transformed = transform_regions(raw_data)

    output_path = os.path.join(STAGING_DIR, f"transformed_{context['ds_nodash']}.json")
    with open(output_path, "w") as f:
        json.dump(transformed, f, default=str)

    context["ti"].xcom_push(key="transformed_path", value=output_path)
    logger.info("Transformed %d records", len(transformed))


def load_clickhouse(**context):
    from source.etl.clickhouse_loader import load_region_statistics

    transformed_path = context["ti"].xcom_pull(task_ids="transform", key="transformed_path")
    with open(transformed_path) as f:
        rows = json.load(f)

    count = load_region_statistics(rows)
    logger.info("Loaded %d rows into ClickHouse", count)


with DAG(
    dag_id="tbb_region_statistics",
    default_args=default_args,
    description="TBB Regional Statistics ETL Pipeline",
    schedule_interval="0 6 1 * *",  # 1st of month, 06:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["tbb", "regions"],
) as dag:

    t_fetch_metadata = PythonOperator(
        task_id="fetch_metadata",
        python_callable=fetch_metadata,
    )

    t_fetch_data = PythonOperator(
        task_id="fetch_data",
        python_callable=fetch_data,
    )

    t_transform = PythonOperator(
        task_id="transform",
        python_callable=transform,
    )

    t_load = PythonOperator(
        task_id="load_clickhouse",
        python_callable=load_clickhouse,
    )

    t_fetch_metadata >> t_fetch_data >> t_transform >> t_load
