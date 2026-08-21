import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error

FEATURE_COLS = [
    "hazard_id", "district_id", "month", "day_of_week",
    "rain_1d", "rain_3d", "rain_7d", "rain_peak_7d",
]
HAZARD_ONLY_COLS = ["hazard_id"]
TARGET_COL = "log_loss"


def load_data():
    df = pd.read_csv("data/loss_dataset.csv")
    df["incident_on"] = pd.to_datetime(df["incident_on"])
    return df


def time_based_split(df, test_fraction=0.2):
    df = df.sort_values("incident_on")
    n_test = max(1, int(len(df) * test_fraction))
    return df.iloc[:-n_test], df.iloc[-n_test:]


def evaluate_model(X_train, y_train, X_test, y_test, run_name, params, real_loss_test):
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(params)
        mlflow.log_param("split_method", "time_based_most_recent_20pct")
        mlflow.log_param("target", "log1p(estimatedLoss)")
        mlflow.log_param("features", ",".join(X_train.columns))

        model = GradientBoostingRegressor(**params)
        model.fit(X_train, y_train)

        pred_log = model.predict(X_test)
        r2 = r2_score(y_test, pred_log)
        mae_log = mean_absolute_error(y_test, pred_log)

        # Back-transformed to real rupees for interpretability -- MAE in
        # log space alone doesn't tell you "how far off in Rs" intuitively.
        pred_real = np.expm1(pred_log)
        mae_real = mean_absolute_error(real_loss_test, pred_real)

        mlflow.log_metric("r2_log_scale", r2)
        mlflow.log_metric("mae_log_scale", mae_log)
        mlflow.log_metric("mae_real_rupees", mae_real)
        mlflow.sklearn.log_model(model, "model")

        print(f"\n=== {run_name} ===")
        print(f"R² (log scale):        {r2:.3f}")
        print(f"MAE (log scale):       {mae_log:.3f}")
        print(f"MAE (real Rs, back-transformed): {mae_real:,.0f}")

        importances = pd.Series(model.feature_importances_, index=X_train.columns)
        importances = importances.sort_values(ascending=False)
        print("Feature importances:")
        print(importances.to_string())

    return model, r2


def train_and_evaluate():
    df = load_data()
    train_df, test_df = time_based_split(df)

    print(f"Train set: {len(train_df)} rows")
    print(f"Test set:  {len(test_df)} rows (most recent ~20% by date)")
    print(f"Test date range: {test_df['incident_on'].min().date()} to {test_df['incident_on'].max().date()}")

    y_train, y_test = train_df[TARGET_COL], test_df[TARGET_COL]
    real_loss_test = test_df["estimated_loss"]

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("bipad-severity-loss")

    params = {
        "n_estimators": 150,
        "max_depth": 4,
        "learning_rate": 0.1,
        "min_samples_leaf": 20,
        "subsample": 0.85,
        "random_state": 42,
    }

    # Same check as the casualty model: does hazard type alone (dominated
    # by Fire at 76% of rows) explain most of the variance, or does
    # district/timing/rainfall add real signal on top?
    _, hazard_only_r2 = evaluate_model(
        train_df[HAZARD_ONLY_COLS], y_train, test_df[HAZARD_ONLY_COLS], y_test,
        "hazard_only_baseline", params, real_loss_test
    )

    full_model, full_r2 = evaluate_model(
        train_df[FEATURE_COLS], y_train, test_df[FEATURE_COLS], y_test,
        "full_features", params, real_loss_test
    )

    print(f"\n=== Comparison ===")
    print(f"Hazard-only baseline R²: {hazard_only_r2:.3f}")
    print(f"Full feature set R²:     {full_r2:.3f}")
    print(f"Lift from district/timing/rainfall: {full_r2 - hazard_only_r2:+.3f}")

    # Regression showed near-zero signal (R² ~0.046, no lift from features).
    # Before concluding this is a full null result, test a coarser framing:
    # tercile-based low/medium/high loss tiers, classified rather than
    # regressed. Parallels the casualty model, where turning a hard problem
    # into classification (rather than exact count/magnitude) revealed real
    # signal. Tercile cuts computed on TRAIN data only, applied to test --
    # avoids leaking test-set distribution info into the tier boundaries.
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import accuracy_score, f1_score as f1_score_multi

    tier_edges = train_df["log_loss"].quantile([1/3, 2/3]).values
    def to_tier(x):
        if x <= tier_edges[0]:
            return 0  # low
        elif x <= tier_edges[1]:
            return 1  # medium
        return 2  # high

    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df["tier"] = train_df["log_loss"].apply(to_tier)
    test_df["tier"] = test_df["log_loss"].apply(to_tier)

    print(f"\n=== Tier framing (low/medium/high, tercile cuts from train) ===")
    print(f"Tier edges (log scale): {tier_edges}")
    print(f"Train tier distribution:\n{train_df['tier'].value_counts().sort_index()}")
    print(f"Test tier distribution:\n{test_df['tier'].value_counts().sort_index()}")

    tier_params = {**params, "max_depth": 4}
    with mlflow.start_run(run_name="tier_classification_full_features"):
        mlflow.log_params(tier_params)
        mlflow.log_param("target", "log_loss tercile (low/medium/high)")
        clf = GradientBoostingClassifier(**tier_params)
        clf.fit(train_df[FEATURE_COLS], train_df["tier"])
        tier_preds = clf.predict(test_df[FEATURE_COLS])
        acc = accuracy_score(test_df["tier"], tier_preds)
        f1_macro = f1_score_multi(test_df["tier"], tier_preds, average="macro")
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("f1_macro", f1_macro)
        mlflow.sklearn.log_model(clf, "model")
        print(f"Tier classification accuracy: {acc:.3f} (baseline random = 0.333)")
        print(f"Tier classification F1 (macro): {f1_macro:.3f}")

    return full_model


if __name__ == "__main__":
    train_and_evaluate()
