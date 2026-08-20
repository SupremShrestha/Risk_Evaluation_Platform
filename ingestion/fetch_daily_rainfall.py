"""
Fetches today's rainfall features (rain_1d, rain_3d, rain_7d, rain_peak_7d)
for all 77 district centroids and upserts into district_daily_rainfall.

Feeds the lead-lag hazard model's live prediction endpoint. Meant to run
daily via Airflow, appended to the existing bipad_daily_ingestion DAG.

District centroids are read directly from incident_rainfall_negatives
(one fixed (lon, lat) per district_id, confirmed 77 distinct centroids for
77 distinct districts) rather than recomputed here -- avoids having two
different centroid-derivation methods in the codebase.

Window convention matches fetch_peak_rainfall.py / build_leadlag_features.py:
for a given target_date, the N-day window is [target_date - N days, target_date),
i.e. the N days STRICTLY BEFORE target_date, not including it. This is why
"today's" prediction uses rainfall data that should already be complete in
CHIRPS by the time this runs (yesterday and earlier), rather than needing
same-day data that may not have landed yet.
"""
import ee
import psycopg2
import psycopg2.extras
import datetime
import argparse
import os

# Reads from env vars when present (matches DB_HOST/DB_PORT/POSTGRES_* already
# injected into the Airflow containers in docker-compose.yml), falling back
# to host-machine defaults for running this manually outside Docker.
DB_KWARGS = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", 5433)),
    user=os.environ.get("POSTGRES_USER", "bipad_admin"),
    password=os.environ.get("POSTGRES_PASSWORD", "changeme_dev_password"),
    dbname=os.environ.get("POSTGRES_DB", "bipad_risk"),
)

ee.Initialize(project="bipad-risk-platform")
chirps = ee.ImageCollection("UCSB-CHC/CHIRPS/V3/DAILY_RNL")


def get_district_centroids():
    conn = psycopg2.connect(**DB_KWARGS)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT ON (district_id) district_id, lon, lat
        FROM incident_rainfall_negatives
        ORDER BY district_id
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_daily_rainfall(target_date):
    """
    target_date: datetime.date -- the day we want features FOR (typically
    today, when run by the daily DAG). Rainfall window is the 7 days before
    this date, not including it.
    """
    districts = get_district_centroids()
    print(f"=== Fetching rainfall features for {target_date}, {len(districts)} districts ===")

    end_excl = target_date
    start_1d = target_date - datetime.timedelta(days=1)
    start_3d = target_date - datetime.timedelta(days=3)
    start_7d = target_date - datetime.timedelta(days=7)

    count_check = chirps.filterDate(str(start_7d), str(end_excl)).size().getInfo()
    if count_check == 0:
        print(f"No CHIRPS coverage for the window ending {target_date}. Skipping "
              f"(known issue: near-real-time CHIRPS backfills with a lag of a "
              f"few weeks -- see known-issues.md).")
        return

    rain_1d_img = chirps.filterDate(str(start_1d), str(end_excl)).sum().rename("rain_1d")
    rain_3d_img = chirps.filterDate(str(start_3d), str(end_excl)).sum().rename("rain_3d")
    rain_7d_img = chirps.filterDate(str(start_7d), str(end_excl)).sum().rename("rain_7d")
    peak_img = chirps.filterDate(str(start_7d), str(end_excl)).max().rename("rain_peak_7d")

    combined = rain_1d_img.addBands([rain_3d_img, rain_7d_img, peak_img])

    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([d["lon"], d["lat"]]), {"district_id": d["district_id"]})
        for d in districts
    ])

    try:
        reduced = combined.reduceRegions(
            collection=fc, reducer=ee.Reducer.first(), scale=5566
        ).getInfo()
    except Exception as e:
        print(f"GEE reduceRegions failed: {e}")
        return

    results = []
    for feat in reduced["features"]:
        props = feat["properties"]
        district_id = props["district_id"]
        r1, r3, r7, rpeak = (
            props.get("rain_1d"), props.get("rain_3d"),
            props.get("rain_7d"), props.get("rain_peak_7d"),
        )
        if None in (r1, r3, r7, rpeak):
            print(f"  district {district_id}: incomplete data, skipping")
            continue
        results.append((district_id, target_date, r1, r3, r7, rpeak))

    if not results:
        print("No districts got complete rainfall data. Nothing to upsert.")
        return

    conn = psycopg2.connect(**DB_KWARGS)
    cur = conn.cursor()
    psycopg2.extras.execute_values(cur, """
        INSERT INTO district_daily_rainfall
            (district_id, sample_date, rain_1d, rain_3d, rain_7d, rain_peak_7d)
        VALUES %s
        ON CONFLICT (district_id, sample_date) DO UPDATE SET
            rain_1d = EXCLUDED.rain_1d,
            rain_3d = EXCLUDED.rain_3d,
            rain_7d = EXCLUDED.rain_7d,
            rain_peak_7d = EXCLUDED.rain_peak_7d,
            ingested_at = now()
    """, results)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Upserted {len(results)} districts for {target_date}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date", type=str, default=None,
        help="Target date YYYY-MM-DD. Defaults to today (UTC)."
    )
    args = parser.parse_args()
    target = (
        datetime.date.fromisoformat(args.date) if args.date
        else datetime.date.today()
    )
    fetch_daily_rainfall(target)
