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
**Random train/test splits overestimate performance for spatiotemporal data --
caught via a deliberate methodology check.** The cascading hazard model above
was first evaluated with an 80/20 *random* stratified split (yielding
ROC-AUC 0.708 after tuning). Re-evaluating under a *time-based* split (train
on all but the most recent ~20% of distinct dates, test only on that unseen
future window) -- consistent with `train.py`'s own stated principle that this
is "the only honest way to evaluate a forecasting model" -- dropped ROC-AUC to
**0.580**. The gap is real, not noise: a random split lets chronologically
adjacent events (the same storm system, similar seasonal conditions a few
days apart) land on both sides of the split, letting the model implicitly
exploit information it wouldn't have at real prediction time. The relative
ranking of rainfall features also shifted under the honest split --
`rain_peak_7d` and `rain_7d` became more important than `month`, whereas
`month` dominated under the random split, suggesting the random-split model
was partly leaning on a seasonal shortcut a true future-unseen test doesn't
allow. **0.580 (time-based split) is the number that should be quoted as this
model's real performance; 0.708 (random split) remains useful only for
comparing model architectures against each other under identical, consistent
methodology, not as the model's honest headline result.**

**MLflow was unpinned in Airflow's `_PIP_ADDITIONAL_REQUIREMENTS`, same class
of risk as the earlier `great-expectations`/`cryptography` incident -- root
cause identified and resolved.** While integrating the lead-lag model into
MLflow tracking, the host `ml/.venv`'s freshly-installed mlflow (3.14.0)
could not read `mlflow.db`'s existing schema revision at all ("no such
revision"). Root cause: `mlflow.db` had actually been migrated by a *newer*
mlflow release (3.15.1, revision `6f8d9c3b2a1e` -- confirmed by pulling
3.15.1's own migration source and finding the revision there but not in
3.14.0's) than what was installed -- not the reverse, and not corruption.
Backed up `mlflow.db` first (`mlflow.db.backup-20260817`, since deleted after
confirming success) before upgrading `ml/.venv` to 3.15.1 and running
`mlflow db upgrade`, which completed cleanly with the original two
experiments and all run history intact and readable via the normal API.
Pinning `mlflow==3.15.1` in Airflow's `_PIP_ADDITIONAL_REQUIREMENTS` then
surfaced a second, real dependency conflict: mlflow 3.15.1 requires
`cryptography>=43.0.0`, incompatible with the `pyopenssl==23.2.0`/
`cryptography==41.0.7` pins from the earlier boto3 drift fix. Resolved by
moving those two pins forward to `pyopenssl==24.2.1`/`cryptography==43.0.3`,
which satisfies both mlflow and the original boto3 constraint. mlflow is now
pinned to `3.15.1` consistently across `ml/.venv`, `requirements.txt`, and
`docker-compose.yml`; the lead-lag model's `train_leadlag.py` now shares the
same `mlflow.db` as `train.py` instead of a separate workaround db.

**Deploying fetch_daily_rainfall.py to Airflow surfaced three real
container-specific issues, all resolved.** (1) Hardcoded host="localhost",
port=5433 in the script -- same class of bug as the known "localhost inside
a container != host" issue; fixed by reading DB_HOST/DB_PORT/POSTGRES_* from
env vars, matching the pattern docker-compose.yml already injects into the
Airflow containers. (2) earthengine-api was never in Airflow's
_PIP_ADDITIONAL_REQUIREMENTS (only existed in the host ingestion/.venv) --
added it. (3) GEE credentials only exist on the host
(~/.config/earthengine/credentials); mounted read-only into both Airflow
containers, and had to loosen the file's permissions to be group/other
readable since it's owned by the host UID but the container runs as UID
50000. Separately: the DAG file itself needed `chmod o+r` after being
replaced -- same permission-mismatch category as the credentials file, not
a new issue.

**Real limitation, not a bug: CHIRPS near-real-time backfill lag means
"today"'s rainfall data usually isn't available yet.** Tested
fetch_daily_rainfall.py for a date ~18 days back and got zero districts with
complete data; a date from months back worked cleanly for all 77 districts.
This means PredictHazardView will 404 for genuinely recent dates until
CHIRPS backfills -- expected behavior given the known coverage-gap issue
documented above, not something to "fix" further.

## Severity/Impact Model (Casualty Classifier)
**Same rigor lesson as the lead-lag model's split correction, this time
catching a misleading headline number rather than an inflated one from a
bad split.**

Built a binary classifier predicting whether an incident involves a death
or injury, using hazard type, district, month, day-of-week, and CHIRPS
rainfall (rain_1d/3d/7d/peak_7d) -- all features knowable at/near incident
time, deliberately excluding other fields from the same raw_data->loss
object used to derive the label (familyAffectedCount, estimatedLoss, etc.
would be leakage from the same outcome). incidents with no matching
incident_rainfall row were dropped (16,880 -> 16,210), matching the
lead-lag model's approach for consistency. Time-based split (most recent
~20% by date) used from the start, applying the lesson already learned
from the lead-lag model rather than re-discovering it.

**Full model scored 0.900 ROC-AUC -- initially looked strong, but a
hazard-only baseline (hazard_id as the sole feature) alone scored 0.880.**
Nearly all the apparent performance came from hazard type recognition, not
genuine prediction from context. Root cause: Snake Bite (99.3% casualty
rate across 1,217 incidents) and High Altitude (99.2% across 251) are
near-tautological categories -- "casualty occurred" is almost definitional
of what qualifies as those incident types in BIPAD's own data, not
something meaningfully predicted. Re-evaluating on only the genuinely
uncertain hazard types (excluding any hazard with >90% casualty rate --
Snake Bite, High Altitude) dropped ROC-AUC to **0.738**, with recall of
only 0.271 (misses ~73% of actual casualty incidents on this harder
subset) and precision of 0.576. **0.738 is the honest, defensible number
for this model's real-world value; 0.900 is misleading if quoted alone,
since it's mostly a two-category lookup effect.** Feature importances on
the hard subset show hazard_id still leads (0.34) but district_id (0.19)
and rainfall features (~0.35 combined) contribute meaningfully more than
on the full dataset -- context genuinely matters once the tautological
cases are removed.

**Practical limitation**: even the honest 0.738 ROC-AUC model has low
recall (0.271) on the hard subset -- not reliable enough on its own to
flag "will this incident involve a casualty" for response prioritization
without further work (class-weighting, threshold tuning, or more features
like time-of-day were not yet explored).

## Economic Loss Regression — Genuine Negative Result
**Unlike the casualty model (where trimming tautological cases revealed
real signal underneath a misleading number), this is a complete null
result across two different framings -- worth documenting as a finding,
not a failure to fix.**

Attempted to predict estimatedLoss (log1p-transformed given extreme skew:
range Rs 1 to Rs 362,000,000, no outlier capping since the catastrophic
tail is exactly what a disaster-risk platform should speak to) for the
5,919 incidents with both a populated estimatedLoss and a matching
incident_rainfall row. Same leakage-free feature set as the casualty
model: hazard_id, district_id, month, day_of_week, rain_1d/3d/7d/peak_7d.

**Continuous regression**: hazard-only baseline R² = 0.046; full feature
set R² = 0.046 (no lift at all, -0.000). District/timing/rainfall added
literally nothing on top of hazard type, and hazard type itself explains
almost none of the variance.

**Coarse tier classification** (low/medium/high loss via train-set
terciles on the log scale, to test whether discretizing -- which worked
for the casualty model -- would reveal signal regression couldn't):
accuracy 0.368 against a 0.333 random baseline for 3 balanced classes.
Barely above chance.

**Conclusion**: estimatedLoss appears to be genuinely unpredictable from
this feature set, under both framings. Likely explanation: it's a
self-reported per-incident figure reflecting what specifically was
damaged/destroyed (property value, individual circumstances) -- information
this dataset doesn't capture at all, unlike casualty risk which correlates
meaningfully with hazard type. Not pursuing further without a genuinely
different feature source (e.g. building/infrastructure inventory data,
which BIPAD doesn't provide). This is a legitimate, honestly-earned
negative result, not an unfinished model.