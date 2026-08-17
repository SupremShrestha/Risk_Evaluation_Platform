import ee
import psycopg2
import psycopg2.extras
import datetime

DB_KWARGS = dict(
    host="localhost", port=5433,
    user="bipad_admin", password="changeme_dev_password",
    dbname="bipad_risk"
)

ee.Initialize(project="bipad-risk-platform")
chirps = ee.ImageCollection("UCSB-CHC/CHIRPS/V3/DAILY_RNL")


def fetch_peak_for_table(table_name, id_col, date_col, update_sql):
    conn = psycopg2.connect(**DB_KWARGS)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"""
        SELECT {id_col} AS row_id, {date_col} AS d, lon, lat
        FROM {table_name}
    """ if table_name == "incident_rainfall_negatives" else f"""
        SELECT ir.{id_col} AS row_id, ir.{date_col} AS d,
               ST_X(i.point) AS lon, ST_Y(i.point) AS lat
        FROM {table_name} ir
        JOIN incidents i ON i.id = ir.{id_col}
        WHERE i.point IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    by_date = {}
    for r in rows:
        by_date.setdefault(r["d"], []).append(r)

    print(f"\n=== {table_name}: {len(rows)} rows across {len(by_date)} dates ===")

    results = []
    skipped = []

    for i, (date, samples) in enumerate(sorted(by_date.items()), 1):
        end_excl = date
        start_7d = date - datetime.timedelta(days=7)

        count_check = chirps.filterDate(str(start_7d), str(end_excl)).size().getInfo()
        if count_check == 0:
            skipped.append(str(date))
            continue

        peak_image = chirps.filterDate(str(start_7d), str(end_excl)).max().rename("rain_peak_7d")

        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([r["lon"], r["lat"]]), {"row_id": r["row_id"]})
            for r in samples
        ])

        try:
            reduced = peak_image.reduceRegions(
                collection=fc, reducer=ee.Reducer.first(), scale=5566
            ).getInfo()
            for feat in reduced["features"]:
                props = feat["properties"]
                val = props.get("first")
                if val is not None:
                    results.append((props["row_id"], val))
        except Exception:
            skipped.append(str(date))

        if i % 50 == 0:
            print(f"  {i}/{len(by_date)} dates processed...")

    print(f"Done. {len(results)} rows got a peak value. {len(skipped)} dates skipped.")

    conn2 = psycopg2.connect(**DB_KWARGS)
    cur2 = conn2.cursor()
    psycopg2.extras.execute_values(cur2, update_sql, results)
    conn2.commit()
    cur2.close()
    conn2.close()
    print(f"Updated {len(results)} rows in {table_name}.")


fetch_peak_for_table(
    "incident_rainfall", "incident_id", "incident_date",
    """
    UPDATE incident_rainfall AS t
    SET rain_peak_7d = v.rain_peak_7d
    FROM (VALUES %s) AS v(incident_id, rain_peak_7d)
    WHERE t.incident_id = v.incident_id
    """
)

fetch_peak_for_table(
    "incident_rainfall_negatives", "id", "sample_date",
    """
    UPDATE incident_rainfall_negatives AS t
    SET rain_peak_7d = v.rain_peak_7d
    FROM (VALUES %s) AS v(id, rain_peak_7d)
    WHERE t.id = v.id
    """
)
