import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, average_precision_score

df = pd.read_csv("data/leadlag_dataset.csv")

# same train/test split we'll reuse for every model in this comparison,
# so results are apples-to-apples across baseline -> logistic -> boosting
train_df, test_df = train_test_split(
    df, test_size=0.2, random_state=42, stratify=df["label"]
)

print(f"Train: {len(train_df)} rows ({train_df['label'].mean():.1%} positive)")
print(f"Test:  {len(test_df)} rows ({test_df['label'].mean():.1%} positive)")

results = []

for feature in ["rain_1d", "rain_3d", "rain_7d"]:
    best_f1 = -1
    best_threshold = None

    # search thresholds using only the TRAIN set, never peek at test here
    candidate_thresholds = np.percentile(train_df[feature], np.arange(5, 100, 5))

    for t in candidate_thresholds:
        preds = (train_df[feature] >= t).astype(int)
        f1 = f1_score(train_df["label"], preds, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t

    # now evaluate that chosen threshold ONCE on the held-out test set
    test_preds = (test_df[feature] >= best_threshold).astype(int)
    precision = precision_score(test_df["label"], test_preds, zero_division=0)
    recall = recall_score(test_df["label"], test_preds, zero_division=0)
    f1 = f1_score(test_df["label"], test_preds, zero_division=0)
    roc_auc = roc_auc_score(test_df["label"], test_df[feature])
    pr_auc = average_precision_score(test_df["label"], test_df[feature])

    results.append({
        "feature": feature,
        "threshold_mm": round(best_threshold, 2),
        "test_precision": round(precision, 3),
        "test_recall": round(recall, 3),
        "test_f1": round(f1, 3),
        "test_roc_auc": round(roc_auc, 3),
        "test_pr_auc": round(pr_auc, 3),
    })

results_df = pd.DataFrame(results)
print("\n=== Threshold Baseline Results (test set) ===")
print(results_df.to_string(index=False))

# also report: what if we just always predicted "no incident"? (sanity floor)
majority_baseline_f1 = f1_score(test_df["label"], np.zeros(len(test_df)), zero_division=0)
print(f"\nFor comparison, always-predict-0 baseline F1: {majority_baseline_f1:.3f}")
print(f"Test set positive rate (what accuracy a lazy always-0 model would get): {1 - test_df['label'].mean():.1%}")
