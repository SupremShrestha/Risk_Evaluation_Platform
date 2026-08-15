import ee
import psycopg2
import psycopg2.extras
import datetime

conn = psycopg2.connect(
    host="localhost", port=5433,
    user="bipad_admin", password="changeme_dev_password",
    dbname="bipad_risk"
)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("""
    SELECT id, incident_on::date AS incident_date, ST_X(point) AS lon, ST_Y(point) AS lat
    FROM incidents
    WHERE point IS NOT NULL AND incident_on IS NOT NULL
""")
rows = cur.fetchall()
cur.close()

by_date = {}
for r in rows:
    by_date.setdefault(r["incident_date"], []).append(r)

print(f"{len(rows)} incidents across {len(by_date)} distinct dates")

ee.Initialize(project="bipad-risk-platform")
chirps = ee.ImageCollection("UCSB-CHC/CHIRPS/V3/DAILY_RNL")

results = []
skipped_dates = []

for i, (date, incidents) in enumerate(sorted(by_date.items()), 1):
    # window ends the day BEFORE the incident (lead-lag, not same-day)
    end_excl = date  # exclusive upper bound = incident date itself
    start_1d = date - datetime.timedelta(days=1)
    start_3d = date - datetime.timedelta(days=3)
    start_7d = date - datetime.timedelta(days=7)

    img_1d = chirps.filterDate(str(start_1d), str(end_excl)).sum().rename("rain_1d")
    img_3d = chirps.filterDate(str(start_3d), str(end_excl)).sum().rename("rain_3d")
    img_7d = chirps.filterDate(str(start_7d), str(end_excl)).sum().rename("rain_7d")

    # skip if the whole window has zero source images (real CHIRPS gap)
    count_check = chirps.filterDate(str(start_1d), str(end_excl)).size().getInfo()
    if count_check == 0:
        skipped_dates.append(str(date))
        if i % 50 == 0:
            print(f"  {i}/{len(by_date)} dates processed...")
        continue

    composite = img_1d.addBands(img_3d).addBands(img_7d)

    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([r["lon"], r["lat"]]), {"incident_id": r["id"]})
        for r in incidents
    ])

    try:
        reduced = composite.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.first(),
            scale=5566
        ).getInfo()

        for feat in reduced["features"]:
            props = feat["properties"]
            results.append((
                props["incident_id"],
                str(date),
                props.get("rain_1d"),
                props.get("rain_3d"),
                props.get("rain_7d"),
            ))
    except Exception as e:
        skipped_dates.append(str(date))

    if i % 50 == 0:
        print(f"  {i}/{len(by_date)} dates processed...")

print(f"\nDone fetching. {len(results)} incidents got rainfall values.")
print(f"{len(skipped_dates)} dates skipped: {skipped_dates}")

conn2 = psycopg2.connect(
    host="localhost", port=5433,
    user="bipad_admin", password="changeme_dev_password",
    dbname="bipad_risk"
)
cur2 = conn2.cursor()
psycopg2.extras.execute_values(
    cur2,
    """
    INSERT INTO incident_rainfall (incident_id, incident_date, rain_1d, rain_3d, rain_7d)
    VALUES %s
    ON CONFLICT (incident_id) DO UPDATE
    SET rain_1d = EXCLUDED.rain_1d,
        rain_3d = EXCLUDED.rain_3d,
        rain_7d = EXCLUDED.rain_7d,
        fetched_at = now()
    """,
    results
)
conn2.commit()
cur2.close()
conn2.close()

print(f"Wrote {len(results)} rows to incident_rainfall.")
