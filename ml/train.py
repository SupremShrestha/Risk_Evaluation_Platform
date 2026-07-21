import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def load_data():
    df = pd.read_csv("data/features.csv")
    return df

def encode_categoricals(df):
    """
    Tree-based models can't use raw text like 'Kathmandu' or 'Landslide'
    directly — we need numbers. Label encoding (assigning each category
    an arbitrary integer) is fine for tree models, unlike linear models,
    since trees just learn "is this category greater/less than that split
    point" without assuming any numeric ordering means something.
    """
    df = df.copy()
    encoders = {}
    for col in ["district", "hazard"]:
        le = LabelEncoder()
        df[f"{col}_encoded"] = le.fit_transform(df[col])
        encoders[col] = le
    return df, encoders

def time_based_split(df):
    """
    Held-out test set = the most recent 3 (year, month) combinations
    present in the data. This simulates 'could the model have predicted
    the recent past using only what it knew before that point' — the
    only honest way to evaluate a forecasting model.
    """
    df = df.sort_values(["year", "month"])
    unique_periods = df[["year", "month"]].drop_duplicates().sort_values(["year", "month"])
    test_periods = unique_periods.tail(3)

    is_test = df.set_index(["year", "month"]).index.isin(
        test_periods.set_index(["year", "month"]).index
    )

    train_df = df[~is_test]
    test_df = df[is_test]
    return train_df, test_df

FEATURE_COLS = [
    "district_encoded", "hazard_encoded", "month",
    "prev_month_count", "historical_month_avg",
]
TARGET_COL = "incident_count"

def train_and_evaluate():
    df = load_data()
    df, encoders = encode_categoricals(df)
    train_df, test_df = time_based_split(df)

    print(f"Train set: {len(train_df)} rows")
    print(f"Test set: {len(test_df)} rows (most recent 3 months)")
    print(f"Test period(s): {sorted(test_df[['year','month']].drop_duplicates().values.tolist())}")

    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL]
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL]

    mlflow.set_experiment("bipad-incident-risk")

    with mlflow.start_run():
        params = {
            "n_estimators": 200,
            "max_depth": 10,
            "min_samples_leaf": 3,
            "random_state": 42,
        }
        mlflow.log_params(params)

        model = RandomForestRegressor(**params)
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        preds = np.clip(preds, 0, None)  # counts can't be negative

        mae = mean_absolute_error(y_test, preds)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        r2 = r2_score(y_test, preds)

        mlflow.log_metric("mae", mae)
        mlflow.log_metric("rmse", rmse)
        mlflow.log_metric("r2", r2)

        mlflow.sklearn.log_model(model, "model")

        print(f"\nMAE:  {mae:.3f}  (avg. how many incidents off, per prediction)")
        print(f"RMSE: {rmse:.3f}")
        print(f"R²:   {r2:.3f}")

        importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
        importances = importances.sort_values(ascending=False)
        print("\nFeature importances:")
        print(importances.to_string())

    return model, encoders

if __name__ == "__main__":
    train_and_evaluate()