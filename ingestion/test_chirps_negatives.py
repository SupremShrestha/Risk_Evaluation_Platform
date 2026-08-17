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
    SELECT id, sample_date, lon, lat
    FROM incident_rainfall_negatives
""")
rows = cur.fetchall()
cur.close()

by_date = {}
for r in rows:
    by_date.setdefault(r["sample_date"], []).append(r)

print(f"{len(rows)} negative samples across {len(by_date)} distinct dates")

ee.Initialize(project="bipad-risk-platform")
chirps = ee.ImageCollection("UCSB-CHC/CHIRPS/V3/DAILY_RNL")

results = []
skipped_dates = []

for i, (date, samples) in enumerate(sorted(by_date.items()), 1):
    end_excl = date
    start_1d = date - datetime.timedelta(days=1)
    start_3d = date - datetime.timedelta(days=3)
    start_7d = date - datetime.timedelta(days=7)

    count_check = chirps.filterDate(str(start_1d), str(end_excl)).size().getInfo()
    if count_check == 0:
        skipped_dates.append(str(date))
        if i % 50 == 0:
            print(f"  {i}/{len(by_date)} dates processed...")
        continue

    img_1d = chirps.filterDate(str(start_1d), str(end_excl)).sum().rename("rain_1d")
    img_3d = chirps.filterDate(str(start_3d), str(end_excl)).sum().rename("rain_3d")
    img_7d = chirps.filterDate(str(start_7d), str(end_excl)).sum().rename("rain_7d")
    composite = img_1d.addBands(img_3d).addBands(img_7d)

    fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([r["lon"], r["lat"]]), {"row_id": r["id"]})
        for r in samples
    ])

    try:
        reduced = composite.reduceRegions(
            collection=fc, reducer=ee.Reducer.first(), scale=5566
        ).getInfo()

        for feat in reduced["features"]:
            props = feat["properties"]
            results.append((
                props["row_id"],
                props.get("rain_1d"),
                props.get("rain_3d"),
                props.get("rain_7d"),
            ))
    except Exception:
        skipped_dates.append(str(date))

    if i % 50 == 0:
        print(f"  {i}/{len(by_date)} dates processed...")

print(f"\nDone fetching. {len(results)} negative samples got rainfall values.")
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
    UPDATE incident_rainfall_negatives AS t
    SET rain_1d = v.rain_1d, rain_3d = v.rain_3d, rain_7d = v.rain_7d
    FROM (VALUES %s) AS v(id, rain_1d, rain_3d, rain_7d)
    WHERE t.id = v.id
    """,
    results
)
conn2.commit()
cur2.close()
conn2.close()

print(f"Updated {len(results)} rows in incident_rainfall_negatives.")
