import os
import mlflow
import mlflow.sklearn
import joblib
from django.conf import settings

MLFLOW_TRACKING_URI = f"sqlite:///{settings.BASE_DIR.parent}/ml/mlflow.db"
EXPERIMENT_NAME = "bipad-incident-risk"

_model = None
_encoders = None
_loaded_run_id = None


def get_latest_run_id():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    runs = mlflow.search_runs(
        experiment_names=[EXPERIMENT_NAME],
        order_by=["start_time DESC"],
        max_results=1,
    )
    if runs.empty:
        raise RuntimeError("No trained model runs found in MLflow.")
    return runs.iloc[0]["run_id"]


def get_model_and_encoders():
    global _model, _encoders, _loaded_run_id

    latest_run_id = get_latest_run_id()

    if _model is None or latest_run_id != _loaded_run_id:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        _model = mlflow.sklearn.load_model(f"runs:/{latest_run_id}/model")

        encoders_path = mlflow.artifacts.download_artifacts(
            f"runs:/{latest_run_id}/encoders.pkl"
        )
        _encoders = joblib.load(encoders_path)
        _loaded_run_id = latest_run_id

    return _model, _encoders


def compute_prediction_features(district_name, hazard_title, target_year, target_month):
    """
    Mirrors the exact feature logic used in ml/build_features.py:
      - prev_month_count: actual incident count in the month before target
      - historical_month_avg: average count for this district+hazard+calendar-month,
        across all prior years of real data
    """
    from .models import Incident

    prev_month = target_month - 1
    prev_year = target_year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    prev_month_count = Incident.objects.filter(
        hazard__title=hazard_title,
        district__title=district_name,
        incident_on__year=prev_year,
        incident_on__month=prev_month,
    ).count()

    historical_counts = (
        Incident.objects.filter(
            hazard__title=hazard_title,
            district__title=district_name,
            incident_on__month=target_month,
        )
        .values("incident_on__year")
        .distinct()
    )
    years_seen = set(row["incident_on__year"] for row in historical_counts)
    if years_seen:
        yearly_counts = [
            Incident.objects.filter(
                hazard__title=hazard_title,
                district__title=district_name,
                incident_on__year=y,
                incident_on__month=target_month,
            ).count()
            for y in years_seen
        ]
        historical_month_avg = sum(yearly_counts) / len(yearly_counts)
    else:
        historical_month_avg = 0.0

    return prev_month_count, historical_month_avg