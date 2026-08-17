import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, classification_report
)

df = pd.read_csv("data/leadlag_dataset.csv")

# IDENTICAL split params to threshold_baseline.py -> same rows in train/test,
# so results are directly comparable across models
train_df, test_df = train_test_split(
    df, test_size=0.2, random_state=42, stratify=df["label"]
)

# --- features: rainfall (scaled) + district as one-hot categorical ---
feature_cols_numeric = ["rain_1d", "rain_3d", "rain_7d"]

train_district_dummies = pd.get_dummies(train_df["district_id"], prefix="district")
test_district_dummies = pd.get_dummies(test_df["district_id"], prefix="district")
# align test columns to train's (in case some district only appears in one split)
test_district_dummies = test_district_dummies.reindex(columns=train_district_dummies.columns, fill_value=0)

scaler = StandardScaler()
train_rain_scaled = pd.DataFrame(
    scaler.fit_transform(train_df[feature_cols_numeric]),
    columns=feature_cols_numeric, index=train_df.index
)
test_rain_scaled = pd.DataFrame(
    scaler.transform(test_df[feature_cols_numeric]),
    columns=feature_cols_numeric, index=test_df.index
)

X_train = pd.concat([train_rain_scaled, train_district_dummies], axis=1)
X_test = pd.concat([test_rain_scaled, test_district_dummies], axis=1)
y_train = train_df["label"]
y_test = test_df["label"]

# --- Model A: rainfall only (directly comparable to the threshold baseline) ---
model_rain_only = LogisticRegression(max_iter=1000, class_weight="balanced")
model_rain_only.fit(train_rain_scaled, y_train)
proba_rain_only = model_rain_only.predict_proba(test_rain_scaled)[:, 1]
preds_rain_only = (proba_rain_only >= 0.5).astype(int)

print("=== Logistic Regression: rainfall features only ===")
print(f"ROC-AUC:  {roc_auc_score(y_test, proba_rain_only):.3f}")
print(f"PR-AUC:   {average_precision_score(y_test, proba_rain_only):.3f}")
print(f"Precision: {precision_score(y_test, preds_rain_only):.3f}")
print(f"Recall:    {recall_score(y_test, preds_rain_only):.3f}")
print(f"F1:        {f1_score(y_test, preds_rain_only):.3f}")
print("\nCoefficients (on standardized features):")
for name, coef in zip(feature_cols_numeric, model_rain_only.coef_[0]):
    print(f"  {name}: {coef:+.4f}")

# --- Model B: rainfall + district ---
model_full = LogisticRegression(max_iter=1000, class_weight="balanced")
model_full.fit(X_train, y_train)
proba_full = model_full.predict_proba(X_test)[:, 1]
preds_full = (proba_full >= 0.5).astype(int)

print("\n=== Logistic Regression: rainfall + district ===")
print(f"ROC-AUC:  {roc_auc_score(y_test, proba_full):.3f}")
print(f"PR-AUC:   {average_precision_score(y_test, proba_full):.3f}")
print(f"Precision: {precision_score(y_test, preds_full):.3f}")
print(f"Recall:    {recall_score(y_test, preds_full):.3f}")
print(f"F1:        {f1_score(y_test, preds_full):.3f}")

print("\n=== Comparison to threshold baseline ===")
print("Threshold baseline (rain_1d >= 0mm): ROC-AUC ~0.514")
print(f"Logistic (rainfall only):            ROC-AUC {roc_auc_score(y_test, proba_rain_only):.3f}")
print(f"Logistic (rainfall + district):      ROC-AUC {roc_auc_score(y_test, proba_full):.3f}")
