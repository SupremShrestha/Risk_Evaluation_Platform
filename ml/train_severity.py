import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score
)

FEATURE_COLS = [
    "hazard_id", "district_id", "month", "day_of_week",
    "rain_1d", "rain_3d", "rain_7d", "rain_peak_7d",
]
HAZARD_ONLY_COLS = ["hazard_id"]
TARGET_COL = "casualty"


def load_data():
    df = pd.read_csv("data/severity_dataset.csv")
    df["incident_on"] = pd.to_datetime(df["incident_on"])
    return df


def time_based_split(df, test_fraction=0.2):
    """
    Same principle as train_leadlag.py: held-out test set is the most
    recent ~20% of incidents by date, not a random sample. Applied from
    the start here rather than discovered as a correction -- the lead-lag
    model already proved random splits overestimate performance on this
    kind of spatiotemporal data, no need to re-learn that lesson.
    """
    df = df.sort_values("incident_on")
    n_test = max(1, int(len(df) * test_fraction))
    train_df = df.iloc[:-n_test]
    test_df = df.iloc[-n_test:]
    return train_df, test_df


def evaluate_model(X_train, y_train, X_test, y_test, run_name, params):
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(params)
        mlflow.log_param("split_method", "time_based_most_recent_20pct")
        mlflow.log_param("features", ",".join(X_train.columns))

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

        print(f"\n=== {run_name} ===")
        print(f"ROC-AUC:   {roc_auc:.3f}")
        print(f"PR-AUC:    {pr_auc:.3f}")
        print(f"Precision: {precision:.3f}")
        print(f"Recall:    {recall:.3f}")
        print(f"F1:        {f1:.3f}")

        importances = pd.Series(model.feature_importances_, index=X_train.columns)
        importances = importances.sort_values(ascending=False)
        print("Feature importances:")
        print(importances.to_string())

    return model, roc_auc


def train_and_evaluate():
    df = load_data()
    train_df, test_df = time_based_split(df)

    print(f"Train set: {len(train_df)} rows")
    print(f"Test set:  {len(test_df)} rows (most recent ~20% by date)")
    print(f"Test date range: {test_df['incident_on'].min().date()} to {test_df['incident_on'].max().date()}")
    print(f"Train casualty rate: {train_df[TARGET_COL].mean():.1%}")
    print(f"Test casualty rate:  {test_df[TARGET_COL].mean():.1%}")

    y_train, y_test = train_df[TARGET_COL], test_df[TARGET_COL]

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("bipad-severity-casualty")

    params = {
        "n_estimators": 150,
        "max_depth": 5,
        "learning_rate": 0.1,
        "min_samples_leaf": 30,
        "subsample": 0.85,
        "random_state": 42,
    }

    # Baseline: hazard type alone. Snake Bite (99.3% casualty rate) and High
    # Altitude (99.2%) are near-tautological -- "casualty occurred" is almost
    # definitional of what qualifies as those incident types, not something
    # meaningfully predicted. This baseline shows how much of the full
    # model's score comes from that near-lookup-table effect alone, versus
    # genuine signal from district/timing/rainfall on top of it.
    _, hazard_only_auc = evaluate_model(
        train_df[HAZARD_ONLY_COLS], y_train, test_df[HAZARD_ONLY_COLS], y_test,
        "hazard_only_baseline", params
    )

    # Full model: hazard + district + timing + rainfall
    full_model, full_auc = evaluate_model(
        train_df[FEATURE_COLS], y_train, test_df[FEATURE_COLS], y_test,
        "full_features", params
    )

    print(f"\n=== Comparison ===")
    print(f"Hazard-only baseline ROC-AUC: {hazard_only_auc:.3f}")
    print(f"Full feature set ROC-AUC:     {full_auc:.3f}")
    print(f"Lift from district/timing/rainfall: {full_auc - hazard_only_auc:+.3f}")

    # Snake Bite (99.3% casualty rate) and High Altitude (99.2%) are
    # near-tautological -- casualty is almost definitional for these
    # categories, not something meaningfully predicted. Re-evaluating on
    # only the genuinely uncertain hazard types shows whether the model has
    # real value where it's actually needed, rather than just inheriting a
    # high score from two easy categories.
    TAUTOLOGICAL_HAZARD_IDS = train_df.loc[
        train_df["hazard_id"].isin(
            df.loc[df["casualty"].groupby(df["hazard_id"]).transform("mean") > 0.9, "hazard_id"].unique()
        ), "hazard_id"
    ].unique()

    hard_train = train_df[~train_df["hazard_id"].isin(TAUTOLOGICAL_HAZARD_IDS)]
    hard_test = test_df[~test_df["hazard_id"].isin(TAUTOLOGICAL_HAZARD_IDS)]

    print(f"\nExcluding near-tautological hazards (>90% casualty rate): "
          f"{len(train_df) - len(hard_train)} train rows, "
          f"{len(test_df) - len(hard_test)} test rows removed")
    print(f"Hard-subset test casualty rate: {hard_test[TARGET_COL].mean():.1%}")

    _, hard_auc = evaluate_model(
        hard_train[FEATURE_COLS], hard_train[TARGET_COL],
        hard_test[FEATURE_COLS], hard_test[TARGET_COL],
        "full_features_excl_tautological_hazards", params
    )

    print(f"\n=== Final Comparison ===")
    print(f"Hazard-only baseline (all hazards):        {hazard_only_auc:.3f}")
    print(f"Full model (all hazards):                  {full_auc:.3f}")
    print(f"Full model (excl. near-tautological cases): {hard_auc:.3f}")

    return full_model


if __name__ == "__main__":
    train_and_evaluate()
