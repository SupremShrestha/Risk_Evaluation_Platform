import os
import mlflow
import mlflow.sklearn
import joblib
from django.conf import settings

MLFLOW_TRACKING_URI = f"sqlite:///{settings.BASE_DIR.parent}/ml/mlflow.db"
EXPERIMENT_NAME = "bipad-incident-risk"
LEADLAG_EXPERIMENT_NAME = "bipad-hazard-leadlag"

_model = None
_encoders = None
_loaded_run_id = None

_leadlag_model = None
_leadlag_loaded_run_id = None


def get_latest_run_id(experiment_name=EXPERIMENT_NAME):
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    runs = mlflow.search_runs(
        experiment_names=[experiment_name],
        order_by=["start_time DESC"],
        max_results=1,
    )
    if runs.empty:
        raise RuntimeError(f"No trained model runs found in MLflow experiment '{experiment_name}'.")
    return runs.iloc[0]["run_id"]


def get_model_and_encoders():
    global _model, _encoders, _loaded_run_id

    latest_run_id = get_latest_run_id(EXPERIMENT_NAME)

    if _model is None or latest_run_id != _loaded_run_id:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        _model = mlflow.sklearn.load_model(f"runs:/{latest_run_id}/model")

        encoders_path = mlflow.artifacts.download_artifacts(
            f"runs:/{latest_run_id}/encoders.pkl"
        )
        _encoders = joblib.load(encoders_path)
        _loaded_run_id = latest_run_id

    return _model, _encoders


def get_leadlag_model():
    """
    No encoders needed here (unlike get_model_and_encoders above) --
    train_leadlag.py uses district_id directly as a numeric FK and month as
    a plain integer, so there's no LabelEncoder artifact logged for this model.
    """
    global _leadlag_model, _leadlag_loaded_run_id

    latest_run_id = get_latest_run_id(LEADLAG_EXPERIMENT_NAME)

    if _leadlag_model is None or latest_run_id != _leadlag_loaded_run_id:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        _leadlag_model = mlflow.sklearn.load_model(f"runs:/{latest_run_id}/model")
        _leadlag_loaded_run_id = latest_run_id

    return _leadlag_model


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


def get_leadlag_features(district_id, target_date):
    """
    Reads the precomputed row from district_daily_rainfall (populated daily
    by ingestion/fetch_daily_rainfall.py via Airflow) rather than calling
    CHIRPS/GEE live -- see the handoff discussion on why live GEE calls
    inside a request path were rejected.

    Returns None if no row exists for this (district_id, target_date) --
    e.g. the daily DAG hasn't run yet for that date, or CHIRPS had a
    coverage gap (see known-issues.md).
    """
    from .models import DistrictDailyRainfall

    try:
        row = DistrictDailyRainfall.objects.get(
            district_id=district_id, sample_date=target_date
        )
    except DistrictDailyRainfall.DoesNotExist:
        return None

    return {
        "rain_1d": float(row.rain_1d),
        "rain_3d": float(row.rain_3d),
        "rain_7d": float(row.rain_7d),
        "rain_peak_7d": float(row.rain_peak_7d),
        "month": target_date.month,
        "district_id": district_id,
    }
