# BIPAD Risk Platform

A production-style disaster risk analytics platform built on real government
data from Nepal's [BIPAD Portal](https://bipadportal.gov.np) — the national
disaster information management system run by NDRRMA. It ingests live incident
data, validates it, trains a seasonal risk-prediction model, and serves live
predictions through a web API and dashboard — fully automated on a schedule.

**Live demo / screenshots:** _(add once deployed)_

## Why this project

Most "government open data" portfolio projects use a clean, well-documented
Kaggle-style CSV. This one doesn't. BIPAD's API has no official documentation,
unreliable pagination, inconsistent field shapes depending on query parameters,
and a placeholder record count (`9223372036854775807` — literally `2^63 - 1`).
Building a reliable pipeline against it meant solving real, undocumented
problems rather than following a tutorial. See
[`docs/known-issues.md`](docs/known-issues.md) for the full list of bugs found
and fixed along the way.

## What it does

- **Ingests** incident data (floods, landslides, fires, snake bites, and more)
  from BIPAD's public API, on a daily schedule
- **Validates** every batch with Great Expectations before it's trusted
- **Stores** it in PostGIS-backed PostgreSQL with proper spatial types and
  referential integrity
- **Trains** a seasonal risk model (district × hazard × month → expected
  incident count) on a rolling weekly schedule, using scikit-learn and MLflow
- **Serves** live predictions through a Django REST API that automatically
  picks up the latest trained model — no manual redeployment needed
- **Visualizes** results in a React dashboard: an interactive risk predictor,
  a recent-incidents table, and a clustered map of incident locations

## The finding that justified the model

Landslide and snake bite incidents in Nepal follow an extremely strong seasonal
pattern tied to the monsoon (June–September) — a ~40x swing between the
quietest and busiest months for landslides alone. This is the empirical basis
for treating "month" and "historical seasonal average" as strong predictive
features, confirmed in the raw data before any model was built.

## Architecture

1. **BIPAD API** (government, undocumented, unreliable pagination) is polled by
   the ingestion pipeline.
2. **Ingestion** (Python, paginated, idempotent) writes validated records into
   **PostgreSQL + PostGIS** (`incidents`, `hazards`, `districts`,
   `municipalities` tables), after passing through **Great Expectations**
   validation.
3. **Feature engineering + Random Forest training** (scikit-learn, MLflow
   tracking) reads from the database on a weekly schedule and produces a
   trained model.
4. **Django REST Framework API** (GeoDjango) serves both raw incident data
   and live predictions — automatically reloading whenever a newer trained
   model becomes available.
5. **React frontend** (risk predictor, incidents table, clustered map)
   consumes the API.

**Orchestration:** Apache Airflow (Docker), two scheduled DAGs:
- `bipad_daily_ingestion` (`@daily`) — ingest → validate
- `bipad_weekly_retrain` (`@weekly`) — build features → retrain

## Tech stack

| Layer | Tools |
|---|---|
| Ingestion | Python, `requests`, `psycopg2` |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Validation | Great Expectations |
| ML | pandas, scikit-learn, MLflow |
| API | Django 6, Django REST Framework, GeoDjango |
| Orchestration | Apache Airflow 2.9 (Docker) |
| Frontend | React, Vite, Leaflet |
| CI | GitHub Actions |
| Containerization | Docker Compose |

## Model

- **Task:** predict expected incident count per (district, hazard, month)
- **Hazards modeled:** Landslide, Snake Bite, Fire, Flood — the four with
  enough historical volume to model meaningfully out of BIPAD's 47 tracked
  hazard types
- **Algorithm:** Random Forest Regressor
- **Evaluation:** time-based holdout (most recent 3 real calendar months held
  out — not a random split, since a random split would leak future
  information into training for this kind of seasonal forecasting problem)
- **Result:** R² ≈ 0.69, MAE ≈ 0.95 incidents
- **Dominant feature:** historical seasonal average for that
  district/hazard/month (~94% of feature importance) — directly reflecting
  the strong monsoon-driven seasonality confirmed in the raw data

## Running it locally

### Prerequisites
Docker, Docker Compose, Python 3.12+ (3.14 works but expect friction with some
ML packages — see `docs/known-issues.md`), Node.js 18+

### 1. Start the database and Airflow stack
```bash
cd docker
cp .env.example .env   # fill in POSTGRES_USER / PASSWORD / DB
docker compose up -d
```

### 2. Run the ingestion pipeline (first time / manual)
```bash
cd ingestion
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python ingest.py
.venv/bin/python load_hazards.py
.venv/bin/python load_geo_lookups.py
.venv/bin/python validate.py
```

### 3. Train the model
```bash
cd ml
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python build_features.py
.venv/bin/python train.py
```

### 4. Run the API
```bash
cd api
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

### 5. Run the frontend
```bash
cd frontend
npm install
npm run dev
```
Visit `http://localhost:5173`.

After the first manual run, Airflow takes over — `bipad_daily_ingestion` and
`bipad_weekly_retrain` keep the data and model current automatically.

## Testing

```bash
cd api && .venv/bin/python manage.py test
cd ingestion && .venv/bin/python test_helpers.py -v
cd ml && .venv/bin/python test_features.py -v
```

All three suites run automatically in CI on every push (`.github/workflows/tests.yml`).

## Project structure
ingestion/ Data pipeline — pulls, parses, validates BIPAD data
ml/ Feature engineering and model training (MLflow-tracked)
api/ Django REST API — serves data and live predictions
frontend/ React dashboard — predictor, table, map
docker/ Docker Compose stack + Airflow DAGs
docs/ Known issues and lessons learned

## What's not done / honest limitations

- Not yet deployed to a public host — runs locally via Docker Compose
- Risk-level bands shown in the UI (Low/Moderate/High) are illustrative
  thresholds, not statistically calibrated
- Only 4 of BIPAD's 47 hazard types are modeled — the rest don't have enough
  historical volume per district/month to model reliably
- See [`docs/known-issues.md`](docs/known-issues.md) for known bugs, fixes,
  and acknowledged design tradeoffs

## Data source & attribution

Incident, hazard, and administrative boundary data from Nepal's
[BIPAD Portal](https://bipadportal.gov.np), built by NDRRMA and Youth
Innovation Lab. Used here for personal/academic portfolio purposes.