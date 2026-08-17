import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score

df = pd.read_csv("data/leadlag_dataset.csv")

train_df, test_df = train_test_split(
    df, test_size=0.2, random_state=42, stratify=df["label"]
)

train_dummies = pd.get_dummies(train_df["district_id"], prefix="district")
test_dummies = pd.get_dummies(test_df["district_id"], prefix="district")
test_dummies = test_dummies.reindex(columns=train_dummies.columns, fill_value=0)

y_train = train_df["label"]
y_test = test_df["label"]

model = LogisticRegression(max_iter=1000, class_weight="balanced")
model.fit(train_dummies, y_train)
proba = model.predict_proba(test_dummies)[:, 1]

print("=== Logistic Regression: district ONLY (no rainfall) ===")
print(f"ROC-AUC:  {roc_auc_score(y_test, proba):.3f}")
print(f"PR-AUC:   {average_precision_score(y_test, proba):.3f}")

print("\n=== Full comparison ===")
print("Threshold baseline (rain only):       ROC-AUC ~0.514")
print("Logistic (rainfall only):             ROC-AUC 0.525")
print(f"Logistic (district only):             ROC-AUC {roc_auc_score(y_test, proba):.3f}")
print("Logistic (rainfall + district):       ROC-AUC 0.617")
