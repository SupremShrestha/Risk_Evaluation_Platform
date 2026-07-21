import os
import mlflow
import mlflow.sklearn
import joblib
from django.conf import settings
from django.db.models import Q
from .models import Incident

MLFLOW_TRACKING_URI = f"sqlite:///{settings.BASE_DIR.parent}/ml/mlflow.db"
MODEL_RUN_ID = "81dfbb0491514717abdc80c1949c6f26"

_model = None
_encoders = None


def get_model_and_encoders():
    """
    Lazy-load the model and encoders once, on first request, and cache
    them at module level. Loading a model from disk on every single
    request would be wasteful — this loads once per server process.
    """
    global _model, _encoders

    if _model is None:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        _model = mlflow.sklearn.load_model(f"runs:/{MODEL_RUN_ID}/model")

        encoders_path = mlflow.artifacts.download_artifacts(
            f"runs:/{MODEL_RUN_ID}/encoders.pkl"
        )
        _encoders = joblib.load(encoders_path)

    return _model, _encoders


def compute_prediction_features(district_name, hazard_title, target_year, target_month):
    """
    Mirrors the exact feature logic used in ml/build_features.py:
      - prev_month_count: actual incident count in the month before target
      - historical_month_avg: average count for this district+hazard+calendar-month,
        across all prior years of real data
    """
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
    # Count incidents per historical year for this district+hazard+month,
    # then average across however many years of data we have
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