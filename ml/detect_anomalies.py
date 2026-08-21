"""
Flags district/hazard/month combinations where actual incident counts
deviate sharply from what the existing RandomForest model predicted --
real spikes worth a second look (data quality issue, or a genuine
anomalous event), not a new model.

Deliberately computed on the SAME held-out test period train.py already
evaluates on (most recent 3 months), not the full training history.
Residuals on training rows would understate anomalies -- the model has
partially fit those patterns already (min_samples_leaf=3, max_depth=10
leave real room for memorization), so "how surprised was the model"
is only an honest question on data it never trained on. Same
out-of-sample discipline as train.py/train_leadlag.py's time-based splits.
"""
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
import joblib

EXPERIMENT_NAME = "bipad-incident-risk"
FEATURE_COLS = [
    "district_encoded", "hazard_encoded", "month",
    "prev_month_count", "historical_month_avg",
]


def get_latest_run_id():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    runs = mlflow.search_runs(
        experiment_names=[EXPERIMENT_NAME],
        order_by=["start_time DESC"],
        max_results=1,
    )
    if runs.empty:
        raise RuntimeError(f"No trained model runs found in '{EXPERIMENT_NAME}'.")
    return runs.iloc[0]["run_id"]


def load_model_and_encoders():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    run_id = get_latest_run_id()
    model = mlflow.sklearn.load_model(f"runs:/{run_id}/model")
    encoders_path = mlflow.artifacts.download_artifacts(f"runs:/{run_id}/encoders.pkl")
    encoders = joblib.load(encoders_path)
    return model, encoders


def time_based_split(df):
    """Identical logic to train.py -- same held-out period, for consistency."""
    df = df.sort_values(["year", "month"])
    unique_periods = df[["year", "month"]].drop_duplicates().sort_values(["year", "month"])
    test_periods = unique_periods.tail(3)
    is_test = df.set_index(["year", "month"]).index.isin(
        test_periods.set_index(["year", "month"]).index
    )
    return df[~is_test], df[is_test]


def detect_anomalies(top_n=15):
    df = pd.read_csv("data/features.csv")
    model, encoders = load_model_and_encoders()

    df = df.copy()
    df["district_encoded"] = encoders["district"].transform(df["district"])
    df["hazard_encoded"] = encoders["hazard"].transform(df["hazard"])

    _, test_df = time_based_split(df)
    test_periods = sorted(test_df[["year", "month"]].drop_duplicates().values.tolist())
    print(f"Evaluating on held-out test period(s): {test_periods}\n")

    preds = model.predict(test_df[FEATURE_COLS])
    preds = np.clip(preds, 0, None)

    result = test_df[["district", "hazard", "year", "month", "incident_count"]].copy()
    result["predicted"] = preds.round(2)
    result["residual"] = result["incident_count"] - result["predicted"]

    # Ratio-based, not just raw residual: a gap of "actual 8 vs predicted 1"
    # is a much bigger surprise than "actual 20 vs predicted 15", even
    # though the raw residual is smaller. +1 smoothing avoids division
    # blowing up when predicted is near zero.
    result["surprise_ratio"] = (result["incident_count"] + 1) / (result["predicted"] + 1)

    print(f"=== Top {top_n} positive spikes (actual >> predicted) ===")
    spikes = result.sort_values("surprise_ratio", ascending=False).head(top_n)
    print(spikes[["district", "hazard", "year", "month", "incident_count", "predicted", "surprise_ratio"]]
          .to_string(index=False))

    print(f"\n=== Top {top_n} under-predictions gone the other way (actual << predicted) ===")
    quiet = result.sort_values("surprise_ratio", ascending=True).head(top_n)
    print(quiet[["district", "hazard", "year", "month", "incident_count", "predicted", "surprise_ratio"]]
          .to_string(index=False))

    result.to_csv("data/anomaly_report.csv", index=False)
    print(f"\nFull results ({len(result)} rows) written to data/anomaly_report.csv")

    return result


if __name__ == "__main__":
    detect_anomalies()
