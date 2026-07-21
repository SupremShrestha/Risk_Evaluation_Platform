import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv("../docker/.env")

TOP_HAZARDS = ["Landslide", "Snake Bite", "Fire", "Flood"]

from sqlalchemy import create_engine

def get_engine():
    uri = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@localhost:5433/"
        f"{os.getenv('POSTGRES_DB')}"
    )
    return create_engine(uri)

def fetch_monthly_counts():
    """One row per (district, hazard, year, month) with the actual incident count."""
    query = """
        SELECT
            d.title AS district,
            h.title AS hazard,
            EXTRACT(YEAR FROM i.incident_on)::INT AS year,
            EXTRACT(MONTH FROM i.incident_on)::INT AS month,
            COUNT(*) AS incident_count
        FROM incidents i
        JOIN districts d ON i.district_id = d.id
        JOIN hazards h ON i.hazard_id = h.id
        WHERE h.title = ANY(%(hazards)s)
        GROUP BY d.title, h.title, year, month
        ORDER BY district, hazard, year, month;
    """
    conn = get_engine()
    df = pd.read_sql(query, conn, params={"hazards": TOP_HAZARDS})
    conn.close()
    return df

def build_full_grid(df):
    """
    The DB query only returns rows where incidents actually happened.
    But 'zero incidents this month' is real, important information for the
    model (e.g. 'Kathmandu, Landslide, January = 0' matters just as much as
    a nonzero count). So we build the FULL grid of every district x hazard x
    year x month combination, and fill missing ones with 0.
    """
    districts = df["district"].unique()
    hazards = df["hazard"].unique()
    years = df["year"].unique()
    months = range(1, 13)

    full_index = pd.MultiIndex.from_product(
        [districts, hazards, years, months],
        names=["district", "hazard", "year", "month"],
    )
    full_grid = pd.DataFrame(index=full_index).reset_index()

    merged = full_grid.merge(
        df, on=["district", "hazard", "year", "month"], how="left"
    )
    merged["incident_count"] = merged["incident_count"].fillna(0).astype(int)
    return merged

def add_features(df):
    df = df.sort_values(["district", "hazard", "year", "month"]).reset_index(drop=True)

    # Lag feature: previous month's count for the same district+hazard
    df["prev_month_count"] = df.groupby(["district", "hazard"])["incident_count"].shift(1)

    # Historical average: average count for this district+hazard+calendar-month
    # across all years (captures "Rolpa's typical July landslide count")
    historical_avg = (
        df.groupby(["district", "hazard", "month"])["incident_count"]
        .transform("mean")
    )
    df["historical_month_avg"] = historical_avg

    # Drop rows where we don't have a previous month (first month per group)
    df = df.dropna(subset=["prev_month_count"])

    return df

if __name__ == "__main__":
    print("Fetching monthly counts from database...")
    raw = fetch_monthly_counts()
    print(f"Fetched {len(raw)} non-zero district/hazard/month combinations.")

    print("Building full grid (including zero-incident months)...")
    grid = build_full_grid(raw)
    print(f"Full grid has {len(grid)} rows.")

    print("Adding lag and historical average features...")
    featured = add_features(grid)
    print(f"Final feature table: {len(featured)} rows.")

    os.makedirs("data", exist_ok=True)
    featured.to_csv("data/features.csv", index=False)
    print("Saved to ml/data/features.csv")

    print("\nSample rows:")
    print(featured.head(10).to_string())