# Known Issues & Lessons Learned

A running log of real bugs found and fixed while building this project — kept as a
reference so they don't get silently reintroduced, and as an honest record of the
debugging that went into this system.

## Ingestion

**BIPAD's pagination `next` field is unreliable.** It can remain non-null even after
all real data has been returned — hit this bug three separate times, across
`ingest.py`, `load_hazards.py`, and `load_geo_lookups.py`. The fix is always the
same: check `if not results: break` before trusting `next`, never rely on `next`
alone to know when to stop paginating.

**URL query strings must be built with `params=dict`, never raw string
concatenation.** The `+` character in ISO datetime strings (e.g.
`2026-06-19T17:02:42+00:00`) gets silently misinterpreted as a space when
concatenated into a URL manually, since `+` is a reserved character meaning "space"
in `application/x-www-form-urlencoded` encoding. `requests.get(url, params=...)`
handles this correctly automatically.

**Fields from the BIPAD API can arrive as either a plain integer ID or a fully
expanded nested object**, depending on whether `expand=` was included in the
request (e.g. `loss` can be `464323` or `{"id": 464323, "deaths": 0, ...}`).
Defensive helper functions (`extract_loss_id`, `extract_hazard_id`) normalize this.

## Database / Schema

**Adding a foreign key to an already-populated table requires the referenced table
to be populated first**, or the constraint fails immediately against existing
mismatched data. Always: create table → populate lookup table → THEN add the FK.

## Django / GeoDjango

**GeoDjango requires `django.contrib.gis.db.backends.postgis` as the database
`ENGINE`**, not the plain `django.db.backends.postgresql` — using the wrong one
causes `AttributeError: 'DatabaseOperations' object has no attribute 'select'` the
moment any spatial field is queried through the ORM.

**Models with `managed = False` get no auto-created tables in Django's ephemeral
test database.** `manage.py test` builds a fresh, empty test DB from migrations —
since unmanaged models generate no `CreateModel` migration operations, their tables
simply don't exist during tests, causing `relation "X" does not exist`. Fixed with
an explicit `migrations.RunSQL(...)` migration that creates the tables regardless
of the `managed` setting.

## ML / Feature Engineering

**The feature grid must be built from actual observed `(year, month)` pairs in the
data, never a full Cartesian product of `all_years × range(1,13)`.** The naive
version silently invented nonexistent months (e.g. Oct–Dec 2026, which hadn't
happened yet, since 2026 only had data through July) with zero-filled counts. This
corrupted both training data and, more seriously, the evaluation holdout — the
model appeared to work (MAE looked fine) while actually being evaluated against
fabricated all-zero months, producing a meaningless R²=0.000 that looked plausible
until inspected closely. Fixed by deriving the grid from
`df[["year","month"]].drop_duplicates()`.

**Training-time and serving-time feature computation must stay in sync.**
`ml/build_features.py` and `api/incidents/ml_service.py::compute_prediction_features`
independently compute `prev_month_count` and `historical_month_avg` — any drift
between the two would silently degrade prediction quality without erroring.

**MLflow bakes the absolute artifact storage path into its tracking database at
experiment-creation time.** Training from a different environment (e.g. inside a
Docker container) than where the experiment was first created requires that exact
original absolute host path to be reachable — not just an equivalent, differently
mounted path. Fixed by mounting the ML folder at both `/opt/airflow/ml` and the
literal original host absolute path inside the Airflow containers.

**Great Expectations major version must match exactly between every environment
that runs `validate.py`.** 0.18.x and 1.x have incompatible `great_expectations.yml`
config schemas — pin the exact version (`great-expectations==0.18.22`) everywhere.

## Docker / Airflow

**The Airflow container runs as a different UID (50000) than the host user.** Any
folder the container needs to write to must be host-writable by "other" users
(`chmod o+w`), including: `docker/airflow/logs/`, `ingestion/gx/` (and its
subfolders), `ml/data/`, `ml/artifacts/`, `ml/mlflow.db` and its *containing
directory* (SQLite needs directory write access for its journal files, not just the
`.db` file itself). `docker/airflow/dags/` is the exception — kept host-owned since
only the host edits DAG files; the container only needs read access.

**`docker compose restart` does not reapply changed environment variables or
`_PIP_ADDITIONAL_REQUIREMENTS`.** Only `docker compose down` + `up -d` (or
`up -d --force-recreate`) actually recreates containers with an updated
`docker-compose.yml`. This cost significant debugging time — a container that
*looked* freshly started could still be running with stale config.

**`localhost` inside a container refers to the container itself, not the host or
other containers.** Cross-container database access must use the Postgres
service's name (`postgres`) and internal port (`5432`), not the host-mapped
`localhost:5433`. All scripts read `DB_HOST`/`DB_PORT` env vars with
`localhost`/`5433` as defaults, so local (non-containerized) runs are unaffected.

## CI

**Importing a module for testing also triggers all of that module's other,
unrelated imports.** `test_features.py` imports `build_full_grid` from
`build_features.py`, which also imports `psycopg2`, `sqlalchemy`, and `dotenv` at
module level for an unrelated function — even though the test never touches the
database. CI dependency lists must cover a module's full import chain, not just
what the specific test logically needs.

## Environment

**Python 3.14 (bleeding-edge at the time of building this) caused repeated
friction**: numpy required a C++ compiler to build from source (no prebuilt wheel
yet), MLflow's own bundled web UI is broken on it entirely (unrelated to this
project — an `importlib.abc.Traversable` import error in MLflow's optional
assistant feature), and Apache Airflow was not run locally at all for this reason —
it runs exclusively inside Docker, sidestepping host Python version compatibility.

## Acknowledged design tradeoffs (not bugs, but worth noting)

- `build_features.py` mixes pure data-transformation logic with I/O
  (database-fetching) in one file. Splitting these would clean up the CI dependency
  issue noted above, but wasn't necessary for this project's scope.
- The frontend's risk-level thresholds (`riskLevel()` in `PredictionTool.jsx`) are
  hand-picked for illustrative purposes, not statistically derived or calibrated.
- Folder permissions between the Airflow container and host are managed with a
  pragmatic `chmod o+w` rather than a more precise shared-group setup — a
  reasonable tradeoff for a solo local-dev project, not how a multi-developer or
  production setup would typically handle it.