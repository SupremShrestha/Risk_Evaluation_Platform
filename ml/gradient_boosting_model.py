import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score
)

df = pd.read_csv("data/leadlag_dataset.csv")
dropped = df["district_id"].isnull().sum()
df = df.dropna(subset=["district_id"])
print(f"Dropped {dropped} rows with missing district_id ({dropped/  (len(df)+dropped):.2%} of data)\n")

df["sample_date"] = pd.to_datetime(df["sample_date"])
df["month"] = df["sample_date"].dt.month

train_df, test_df = train_test_split(
    df, test_size=0.2, random_state=42, stratify=df["label"]
)

feature_cols = ["rain_1d", "rain_3d", "rain_7d", "rain_peak_7d", "month", "district_id"]
X_train = train_df[feature_cols]
X_test = test_df[feature_cols]
y_train = train_df["label"]
y_test = test_df["label"]

model = GradientBoostingClassifier(random_state=42)
model.fit(X_train, y_train)

proba = model.predict_proba(X_test)[:, 1]
preds = (proba >= 0.5).astype(int)

print("=== Gradient Boosting: rainfall + district ===")
print(f"ROC-AUC:   {roc_auc_score(y_test, proba):.3f}")
print(f"PR-AUC:    {average_precision_score(y_test, proba):.3f}")
print(f"Precision: {precision_score(y_test, preds):.3f}")
print(f"Recall:    {recall_score(y_test, preds):.3f}")
print(f"F1:        {f1_score(y_test, preds):.3f}")

print("\nFeature importances:")
for name, imp in sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]):
    print(f"  {name}: {imp:.3f}")

print("\n=== Full model comparison (test ROC-AUC) ===")
print("Threshold baseline (rain only):     0.514")
print("Logistic (rainfall only):           0.525")
print("Logistic (district only):           0.604")
print("Logistic (rainfall + district):     0.617")
print(f"Gradient Boosting (rain+district):  {roc_auc_score(y_test, proba):.3f}")