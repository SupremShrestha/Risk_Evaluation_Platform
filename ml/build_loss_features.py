"""
Builds the training dataset for the economic loss regression model:
predicts log(estimatedLoss + 1) for incidents where it's populated, using
the same leakage-free feature set as the casualty classifier (hazard,
district, timing, rainfall) -- not other raw_data->loss fields, which are
outcomes of the same event.

Only incidents with a non-null estimatedLoss AND a matching incident_rainfall
row are included, same rainfall-match requirement as the casualty dataset
for consistency.

No outlier capping -- log-transform only. The catastrophic tail (e.g. the
362M flood event) is exactly what a disaster-risk platform should be able
to speak to, not something to discard as noise.
"""
import psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np

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
            (i.raw_data->'loss'->>'estimatedLoss')::numeric AS estimated_loss
        FROM incidents i
        JOIN incident_rainfall ir ON ir.incident_id = i.id
        WHERE i.hazard_id IS NOT NULL
          AND i.district_id IS NOT NULL
          AND i.incident_on IS NOT NULL
          AND i.raw_data->'loss'->>'estimatedLoss' IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows)
    print(f"Raw rows (with rainfall match + estimatedLoss present): {len(df)}")

    df["incident_on"] = pd.to_datetime(df["incident_on"])
    df["month"] = df["incident_on"].dt.month
    df["day_of_week"] = df["incident_on"].dt.dayofweek
    df["log_loss"] = np.log1p(df["estimated_loss"].astype(float))

    print(f"estimatedLoss range: {df['estimated_loss'].min():.0f} to {df['estimated_loss'].max():.0f}")
    print(f"log_loss range: {df['log_loss'].min():.2f} to {df['log_loss'].max():.2f}")

    df = df[[
        "incident_id", "incident_on", "hazard_id", "district_id",
        "month", "day_of_week", "rain_1d", "rain_3d", "rain_7d", "rain_peak_7d",
        "estimated_loss", "log_loss",
    ]]

    df.to_csv("data/loss_dataset.csv", index=False)
    print(f"Wrote {len(df)} rows to data/loss_dataset.csv")
    return df


if __name__ == "__main__":
    build_dataset()
