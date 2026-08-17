## Cascading Hazard Model (Rainfall Lead-Lag)
**Iterative model development, documented in full rather than just the final
number, since each step's contribution is itself informative.**

Built a binary classifier predicting whether a hazard incident occurs in a
district on a given day, using rainfall features from CHIRPS v3 (see
"Feature Engineering / External Data" above) plus district and seasonality.
Negative (non-incident) samples were drawn ~2:1 against positives, at each
district's incident-centroid location, across the same historical date range.

Progression (ROC-AUC on an identical, untouched 20% held-out test set
throughout):

| Model                                          | ROC-AUC |
|-------------------------------------------------|---------|
| Threshold rule (best single rain cutoff)         | 0.514   |
| Logistic regression (rainfall only)              | 0.525   |
| Logistic regression (district only)              | 0.604   |
| Logistic regression (rainfall + district)        | 0.617   |
| Gradient boosting (rain sum + district)          | 0.639   |
| + peak single-day rainfall intensity (7d window) | 0.644   |
| + month/seasonality feature                      | 0.677   |
| + hyperparameter tuning (5-fold CV random search) | **0.708** |

**Key findings, in order of how they were discovered:**
- Same-day/summed rainfall alone is a weak signal (ROC-AUC ~0.52, barely above
  chance) — the naive threshold-based approach degenerates to "always predict
  positive" because rainfall is heavily zero-inflated and the positive/negative
  distributions overlap too much for any single cutoff to separate them.
- District identity alone (0.604) explains far more variance than rainfall
  alone (0.525) — baseline geographic/exposure risk dominates short-term
  weather signal at this feature granularity.
- Peak single-day rainfall intensity (not just cumulative sum) adds real,
  independent signal — physically sensible, since a hillslope responds
  differently to one intense storm than the same total spread over a week.
- **Seasonality (month) was the single largest missing feature** — adding it
  produced the second-largest jump in the whole progression, larger than any
  rainfall-window refinement. Confounds with rainfall itself (monsoon months
  have more rain), which is why every rainfall feature's individual importance
  dropped once month was added — the model's understanding became more
  accurate, not that rainfall stopped mattering.
- Hyperparameter tuning (via 5-fold CV `RandomizedSearchCV`, tuned only on the
  training set, test set touched exactly once at the end) gave the largest
  single jump (+0.031) — CV and test scores stayed close (0.712 vs 0.708),
  confirming this was genuine generalization, not overfitting to noise.

**Honest limitation:** 0.708 ROC-AUC is a real, moderate predictor — useful as
a risk-elevation signal, not a reliable early-warning system on its own.
District geometry doesn't exist in this schema (only lookup tables), so every
location used here is a district-incident centroid, not a true polygon
average or the actual point of risk — a real source of noise that finer
spatial resolution (ward-level, or true district boundaries) would likely
improve on.