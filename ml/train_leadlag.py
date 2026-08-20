import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score
)

def load_data():
    df = pd.read_csv("data/leadlag_dataset.csv")
    df = df.dropna(subset=["district_id"])  # ~0.17% of rows lack a district; can't be used
    df["sample_date"] = pd.to_datetime(df["sample_date"])
    df["month"] = df["sample_date"].dt.month
    return df

def time_based_split(df, test_fraction=0.2):
    """
    Held-out test set = the most recent ~20% of distinct sample_dates present
    in the data. Mirrors train.py's 'most recent N periods held out' approach,
    scaled to this dataset's daily (not monthly) granularity. This is the only
    honest way to evaluate a forecasting model -- a random split would let the
    model implicitly train on conditions chronologically after some test dates
    (e.g. a similar storm system a few days later ending up in train), which
    isn't information a real deployment would have at prediction time.
    """
    unique_dates = sorted(df["sample_date"].unique())
    n_test_dates = max(1, int(len(unique_dates) * test_fraction))
    test_dates = set(unique_dates[-n_test_dates:])

    is_test = df["sample_date"].isin(test_dates)
    train_df = df[~is_test]
    test_df = df[is_test]
    return train_df, test_df

# Note: unlike train.py, no LabelEncoder / encoders.pkl needed here --
# district_id is already a numeric FK, and month is derived as an integer.
# Nothing in this feature set is free-text, so there's no categorical
# encoding step or artifact to persist for serving.
FEATURE_COLS = ["rain_1d", "rain_3d", "rain_7d", "rain_peak_7d", "month", "district_id"]
TARGET_COL = "label"

def train_and_evaluate():
    df = load_data()
    train_df, test_df = time_based_split(df)

    print(f"Train set: {len(train_df)} rows")
    print(f"Test set:  {len(test_df)} rows (most recent ~20% of distinct dates)")
    print(f"Test date range: {test_df['sample_date'].min().date()} to {test_df['sample_date'].max().date()}")
    print(f"Train positive rate: {train_df[TARGET_COL].mean():.1%}")
    print(f"Test positive rate:  {test_df[TARGET_COL].mean():.1%}")

    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL]
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL]

    # Uses a SEPARATE tracking database from the existing model's mlflow.db.
    # Discovered during this run: mlflow is unpinned in Airflow's
    # _PIP_ADDITIONAL_REQUIREMENTS (docker-compose.yml), and this host venv's
    # freshly-installed mlflow (3.14.0) can't read mlflow.db's schema revision
    # at all ("no such revision") -- meaning there's no reliable single mlflow
    # version this project can currently assume across host/container. Forcing
    # a migration against an assumed-compatible version risks corrupting the
    # existing model's real run history for uncertain gain. See known-issues.md.
    mlflow.set_tracking_uri("sqlite:///mlflow_leadlag.db")
    mlflow.set_experiment("bipad-hazard-leadlag")

    with mlflow.start_run():
        # hyperparameters found via 5-fold CV RandomizedSearchCV under the
        # earlier random-split evaluation -- kept as-is here rather than
        # re-tuned, since re-tuning under time-based CV is a reasonable
        # future improvement but a separate piece of work from this split fix
        params = {
            "n_estimators": 150,
            "max_depth": 5,
            "learning_rate": 0.2,
            "min_samples_leaf": 50,
            "subsample": 0.85,
            "random_state": 42,
        }
        mlflow.log_params(params)
        mlflow.log_param("split_method", "time_based_most_recent_20pct_dates")

        model = GradientBoostingClassifier(**params)
        model.fit(X_train, y_train)

        proba = model.predict_proba(X_test)[:, 1]
        preds = (proba >= 0.5).astype(int)

        roc_auc = roc_auc_score(y_test, proba)
        pr_auc = average_precision_score(y_test, proba)
        precision = precision_score(y_test, preds, zero_division=0)
        recall = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)

        mlflow.log_metric("roc_auc", roc_auc)
        mlflow.log_metric("pr_auc", pr_auc)
        mlflow.log_metric("precision", precision)
        mlflow.log_metric("recall", recall)
        mlflow.log_metric("f1", f1)

        mlflow.sklearn.log_model(model, "model")

        print(f"\nROC-AUC:   {roc_auc:.3f}")
        print(f"PR-AUC:    {pr_auc:.3f}")
        print(f"Precision: {precision:.3f}")
        print(f"Recall:    {recall:.3f}")
        print(f"F1:        {f1:.3f}")

        importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
        importances = importances.sort_values(ascending=False)
        print("\nFeature importances:")
        print(importances.to_string())

    return model

if __name__ == "__main__":
    train_and_evaluate()