"""
Builds the training dataset for the casualty severity classifier:
predicts whether an incident involves a death or injury, given features
knowable at/near the time of the incident (hazard, district, timing,
rainfall) -- NOT other fields from the same raw_data->loss object used to
derive the label (familyAffectedCount, estimatedLoss, etc. would be
leakage, since they're outcomes of the same event, not predictors).

Only uses hazard_id/district_id directly as numeric FKs (no LabelEncoder/
encoders.pkl needed) -- same simplification as ml/train_leadlag.py.

Incidents with no matching incident_rainfall row are dropped, matching the
lead-lag model's approach for consistency across extension models. This
only filters this dataset -- doesn't touch incident_rainfall or any
existing model.
"""
import psycopg2
import psycopg2.extras
import pandas as pd

DB_KWARGS = dict(
    host="localhost", port=5433,
    user="bipad_admin", password="changeme_dev_password",
    dbname="bipad_risk"
)


def build_dataset():
    conn = psycopg2.connect(**DB_KWARGS)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            i.id AS incident_id,
            i.hazard_id,
            i.district_id,
            i.incident_on,
            ir.rain_1d, ir.rain_3d, ir.rain_7d, ir.rain_peak_7d,
            COALESCE((i.raw_data->'loss'->>'peopleDeathCount')::int, 0) AS death_count,
            COALESCE((i.raw_data->'loss'->>'peopleInjuredCount')::int, 0) AS injured_count
        FROM incidents i
        JOIN incident_rainfall ir ON ir.incident_id = i.id
        WHERE i.hazard_id IS NOT NULL
          AND i.district_id IS NOT NULL
          AND i.incident_on IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows)
    print(f"Raw rows (with rainfall match): {len(df)}")

    df["incident_on"] = pd.to_datetime(df["incident_on"])
    df["month"] = df["incident_on"].dt.month
    df["day_of_week"] = df["incident_on"].dt.dayofweek  # 0=Monday
    df["casualty"] = ((df["death_count"] > 0) | (df["injured_count"] > 0)).astype(int)

    print(f"Casualty positive rate: {df['casualty'].mean():.1%}")

    df = df[[
        "incident_id", "incident_on", "hazard_id", "district_id",
        "month", "day_of_week", "rain_1d", "rain_3d", "rain_7d", "rain_peak_7d",
        "casualty",
    ]]

    df.to_csv("data/severity_dataset.csv", index=False)
    print(f"Wrote {len(df)} rows to data/severity_dataset.csv")
    return df


if __name__ == "__main__":
    build_dataset()
