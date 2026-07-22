from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "suprem",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="bipad_daily_ingestion",
    default_args=default_args,
    description="Daily ingestion and validation of BIPAD incident data",
    schedule_interval="@daily",
    start_date=datetime(2026, 7, 20),
    catchup=False,   # don't backfill missed runs if the scheduler was off
    tags=["bipad", "ingestion"],
) as dag:

    ingest_task = BashOperator(
        task_id="ingest_incidents",
        bash_command="cd /opt/airflow/ingestion && python ingest.py",
    )

    validate_task = BashOperator(
        task_id="validate_incidents",
        bash_command="cd /opt/airflow/ingestion && python validate.py",
    )

    ingest_task >> validate_task