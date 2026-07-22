from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "suprem",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="bipad_weekly_retrain",
    default_args=default_args,
    description="Weekly retraining of the incident risk model on updated data",
    schedule_interval="@weekly",
    start_date=datetime(2026, 7, 20),
    catchup=False,
    tags=["bipad", "ml", "training"],
) as dag:

    build_features_task = BashOperator(
        task_id="build_features",
        bash_command="cd /opt/airflow/ml && python build_features.py",
    )

    train_task = BashOperator(
        task_id="train_model",
        bash_command="cd /opt/airflow/ml && python train.py",
    )

    build_features_task >> train_task