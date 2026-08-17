import pandas as pd
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score
)

df = pd.read_csv("data/leadlag_dataset.csv")
dropped = df["district_id"].isnull().sum()
df = df.dropna(subset=["district_id"])
print(f"Dropped {dropped} rows with missing district_id\n")

df["sample_date"] = pd.to_datetime(df["sample_date"])
df["month"] = df["sample_date"].dt.month

feature_cols = ["rain_1d", "rain_3d", "rain_7d", "rain_peak_7d", "month", "district_id"]

train_df, test_df = train_test_split(
    df, test_size=0.2, random_state=42, stratify=df["label"]
)
X_train = train_df[feature_cols]
X_test = test_df[feature_cols]
y_train = train_df["label"]
y_test = test_df["label"]

# search space: modest ranges, not exhaustive -- this is a ~50k row dataset,
# no need for huge trees or huge estimator counts
param_dist = {
    "n_estimators": [100, 150, 200, 300],
    "max_depth": [2, 3, 4, 5],
    "learning_rate": [0.01, 0.05, 0.1, 0.2],
    "min_samples_leaf": [5, 10, 20, 50],
    "subsample": [0.7, 0.85, 1.0],
}

# tune on ROC-AUC via 5-fold CV, using ONLY the training set --
# test set stays completely untouched until the very end
search = RandomizedSearchCV(
    GradientBoostingClassifier(random_state=42),
    param_distributions=param_dist,
    n_iter=30,
    scoring="roc_auc",
    cv=5,
    random_state=42,
    n_jobs=-1,
    verbose=1,
)
search.fit(X_train, y_train)

print(f"\nBest CV ROC-AUC (train folds): {search.best_score_:.3f}")
print(f"Best params: {search.best_params_}")

# evaluate the tuned model ONCE on the held-out test set
best_model = search.best_estimator_
proba = best_model.predict_proba(X_test)[:, 1]
preds = (proba >= 0.5).astype(int)

print("\n=== Tuned Gradient Boosting: test set performance ===")
print(f"ROC-AUC:   {roc_auc_score(y_test, proba):.3f}")
print(f"PR-AUC:    {average_precision_score(y_test, proba):.3f}")
print(f"Precision: {precision_score(y_test, preds):.3f}")
print(f"Recall:    {recall_score(y_test, preds):.3f}")
print(f"F1:        {f1_score(y_test, preds):.3f}")

print("\nFeature importances:")
for name, imp in sorted(zip(feature_cols, best_model.feature_importances_), key=lambda x: -x[1]):
    print(f"  {name}: {imp:.3f}")

print("\n=== Full comparison ===")
print("Logistic (rainfall + district):        0.617")
print("Gradient Boosting (sum, default):       0.639")
print("Gradient Boosting (sum+peak, default):  0.644")
print("Gradient Boosting (+ month, default):   0.677")
print(f"Gradient Boosting (+ month, TUNED):     {roc_auc_score(y_test, proba):.3f}")
