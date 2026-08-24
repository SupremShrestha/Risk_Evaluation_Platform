"""
Data-driven spatial hotspot clustering via DBSCAN, run separately per
hazard type -- not aggregated to administrative wards/municipalities,
since neither table in this schema has geometry (confirmed: municipalities
has no geometry column, no ward-level granularity at all). Clustering
directly on incidents.point instead produces real, data-driven hotspots
rather than hotspots forced into arbitrary admin boundaries -- arguably
more informative, and doesn't depend on data this project doesn't have.

Uses haversine distance (real km on Earth's surface), not raw lat/lon
degrees -- degrees distort badly at Nepal's latitude (~27-30°N), where
1 degree of longitude is meaningfully shorter than 1 degree of latitude.
Clustered per hazard type separately: pooling all hazards together would
blend genuinely different spatial patterns (Landslide follows hilly
terrain, Flood follows river basins, Fire is more population-driven) into
meaningless combined clusters.

Results are stored in incident_hotspots (Postgres), replacing all
existing clusters for a hazard on each run -- DBSCAN cluster labels
aren't stable across runs, so this is a precomputed/refreshed-on-schedule
table (meant for the weekly retrain DAG), not a daily append.
"""
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from sklearn.cluster import DBSCAN

DB_KWARGS = dict(
    host="localhost", port=5433,
    user="bipad_admin", password="changeme_dev_password",
    dbname="bipad_risk"
)

EARTH_RADIUS_KM = 6371.0

# eps in km: incidents within this distance of each other (via chain
# reachability, not just pairwise) are considered part of the same hotspot.
# min_samples: minimum incidents to form a real cluster, not noise.
# Tuned per hazard type below since volume varies hugely (Fire has ~7,600
# incidents vs Earthquake's ~90) -- one fixed min_samples would either
# swamp low-volume hazards with noise-only "clusters" or under-cluster
# high-volume ones.
HAZARD_PARAMS = {
    "Landslide":  {"eps_km": 5,  "min_samples": 8},
    "Flood":      {"eps_km": 8,  "min_samples": 6},
    "Fire":       {"eps_km": 3,  "min_samples": 15},
    "Snake Bite": {"eps_km": 5,  "min_samples": 10},
    "Thunderbolt":{"eps_km": 8,  "min_samples": 6},
    "Wind Storm": {"eps_km": 10, "min_samples": 6},
}


def fetch_points(hazard_title):
    conn = psycopg2.connect(**DB_KWARGS)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT i.id AS incident_id, d.title AS district,
               ST_Y(i.point) AS lat, ST_X(i.point) AS lon
        FROM incidents i
        JOIN hazards h ON h.id = i.hazard_id
        LEFT JOIN districts d ON d.id = i.district_id
        WHERE h.title = %(hazard)s AND i.point IS NOT NULL
    """, {"hazard": hazard_title})
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return pd.DataFrame(rows)


def cluster_hazard(hazard_title, eps_km, min_samples):
    df = fetch_points(hazard_title)
    if len(df) < min_samples:
        print(f"{hazard_title}: only {len(df)} points, skipping (below min_samples={min_samples}).")
        return None

    coords_rad = np.radians(df[["lat", "lon"]].values)
    eps_rad = eps_km / EARTH_RADIUS_KM

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine")
    labels = db.fit_predict(coords_rad)
    df["cluster"] = labels

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    print(f"\n=== {hazard_title} ({len(df)} points, eps={eps_km}km, min_samples={min_samples}) ===")
    print(f"Clusters found: {n_clusters}. Noise points (not in any cluster): {n_noise} ({n_noise/len(df):.1%})")

    return df


def get_district_id_lookup():
    conn = psycopg2.connect(**DB_KWARGS)
    cur = conn.cursor()
    cur.execute("SELECT title, id FROM districts")
    lookup = dict(cur.fetchall())
    cur.close()
    conn.close()
    return lookup


def get_hazard_id(hazard_title):
    conn = psycopg2.connect(**DB_KWARGS)
    cur = conn.cursor()
    cur.execute("SELECT id FROM hazards WHERE title = %s", (hazard_title,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def store_clusters(hazard_title, cluster_summary, district_lookup):
    """
    DBSCAN cluster labels aren't stable across runs (a re-run with slightly
    different data can renumber clusters entirely) -- so this replaces ALL
    existing clusters for a hazard on each run, rather than upserting by
    label. Correct for a precomputed/refreshed-on-schedule table, not a
    daily append like district_daily_rainfall.
    """
    hazard_id = get_hazard_id(hazard_title)
    if hazard_id is None:
        print(f"  Could not find hazard_id for '{hazard_title}', skipping storage.")
        return

    rows = []
    for cluster_label, row in cluster_summary.iterrows():
        district_id = district_lookup.get(row["dominant_district"])
        rows.append((
            hazard_id, int(cluster_label), int(row["size"]),
            float(row["center_lat"]), float(row["center_lon"]), district_id,
        ))

    conn = psycopg2.connect(**DB_KWARGS)
    cur = conn.cursor()
    cur.execute("DELETE FROM incident_hotspots WHERE hazard_id = %s", (hazard_id,))
    psycopg2.extras.execute_values(cur, """
        INSERT INTO incident_hotspots
            (hazard_id, cluster_label, size, center_lat, center_lon, dominant_district_id)
        VALUES %s
    """, rows)
    conn.commit()
    cur.close()
    conn.close()
    print(f"  Stored {len(rows)} clusters for {hazard_title} in incident_hotspots.")


def run_all():
    district_lookup = get_district_id_lookup()
    all_results = {}
    for hazard, params in HAZARD_PARAMS.items():
        result = cluster_hazard(hazard, params["eps_km"], params["min_samples"])
        if result is None or not (result["cluster"] != -1).any():
            continue

        all_results[hazard] = result
        result.to_csv(f"data/hotspots_{hazard.lower().replace(' ', '_')}.csv", index=False)

        cluster_summary = (
            result[result["cluster"] != -1]
            .groupby("cluster")
            .agg(
                size=("incident_id", "count"),
                center_lat=("lat", "mean"),
                center_lon=("lon", "mean"),
                dominant_district=("district", lambda x: x.mode().iloc[0] if not x.mode().empty else None),
            )
        )
        store_clusters(hazard, cluster_summary, district_lookup)

    return all_results


if __name__ == "__main__":
    run_all()