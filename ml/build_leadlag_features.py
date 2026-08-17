import os
import pandas as pd
from sqlalchemy import create_engine

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_USER = os.getenv("DB_USER", "bipad_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme_dev_password")
DB_NAME = os.getenv("DB_NAME", "bipad_risk")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

positives = pd.read_sql("""
    SELECT
        ir.incident_id AS row_id,
        i.district_id,
        ir.incident_date AS sample_date,
        ir.rain_1d,
        ir.rain_3d,
        ir.rain_7d,
        ir.rain_peak_7d,
        1 AS label
    FROM incident_rainfall ir
    JOIN incidents i ON i.id = ir.incident_id
    WHERE ir.rain_1d IS NOT NULL
      AND ir.rain_3d IS NOT NULL
      AND ir.rain_7d IS NOT NULL
      AND ir.rain_peak_7d IS NOT NULL
""", engine)

negatives = pd.read_sql("""
    SELECT
        id AS row_id,
        district_id,
        sample_date,
        rain_1d,
        rain_3d,
        rain_7d,
        rain_peak_7d,
        0 AS label
    FROM incident_rainfall_negatives
    WHERE rain_1d IS NOT NULL
      AND rain_3d IS NOT NULL
      AND rain_7d IS NOT NULL
      AND rain_peak_7d IS NOT NULL
""", engine)

print(f"Positives: {len(positives)} rows")
print(f"Negatives: {len(negatives)} rows")

combined = pd.concat([positives, negatives], ignore_index=True)

# sanity checks before saving anything
assert combined["label"].isin([0, 1]).all(), "Unexpected label values found"
assert combined[["rain_1d", "rain_3d", "rain_7d"]].isnull().sum().sum() == 0, "Nulls slipped through the WHERE filters"
assert (combined["rain_7d"] >= combined["rain_3d"]).all(), "rain_7d < rain_3d violation in combined data"
assert (combined["rain_3d"] >= combined["rain_1d"]).all(), "rain_3d < rain_1d violation in combined data"

print(f"\nCombined dataset: {len(combined)} rows")
print(f"Label balance: {combined['label'].value_counts().to_dict()}")
print(f"Districts represented: {combined['district_id'].nunique()}")

os.makedirs("data", exist_ok=True)
out_path = "data/leadlag_dataset.csv"
combined.to_csv(out_path, index=False)
print(f"\nSaved to {out_path}")
