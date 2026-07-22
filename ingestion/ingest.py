import os
import time
import random
import logging
from datetime import datetime, timedelta, timezone

import requests
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / "docker" / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://bipadportal.gov.np/api/v1/incident/"
PAGE_SIZE = 100
MAX_RETRIES = 5


def build_initial_params(days_back: int) -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days_back)

    def fmt(dt):
        return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    return {
        "expand": "loss,event,wards",
        "ordering": "-incident_on",
        "limit": PAGE_SIZE,
        "data_source": "drr_api",
        "incident_on__gt": fmt(start),
        "incident_on__lt": fmt(now),
    }


def fetch_page(url: str, params: dict = None) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 429:
                raise requests.exceptions.RequestException("Rate limited (429)")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRIES:
                logger.error(f"Giving up after {MAX_RETRIES} attempts: {e}")
                raise
            backoff = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(
                f"Request failed (attempt {attempt}/{MAX_RETRIES}): {e}. "
                f"Retrying in {backoff:.1f}s"
            )
            time.sleep(backoff)


def extract_loss_id(loss):
    """loss can be a plain int ID, a full nested object, or None."""
    if loss is None:
        return None
    if isinstance(loss, dict):
        return loss.get("id")
    return loss


def extract_hazard_id(hazard):
    """hazard is usually an int, but be defensive in case expand changes this too."""
    if isinstance(hazard, dict):
        return hazard.get("id")
    return hazard


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def upsert_incident(cur, incident: dict):
    point = incident.get("point") or {}
    coords = point.get("coordinates")
    point_wkt = f"SRID=4326;POINT({coords[0]} {coords[1]})" if coords else None

    cur.execute(
        """
        INSERT INTO incidents (
            id, title, title_ne, hazard_id, incident_on, reported_on,
            verified, approved, source, data_source, point, loss_id,
            created_on, modified_on, raw_data
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            verified = EXCLUDED.verified,
            approved = EXCLUDED.approved,
            modified_on = EXCLUDED.modified_on,
            raw_data = EXCLUDED.raw_data;
        """,
        (
            incident["id"],
            incident.get("title"),
            incident.get("titleNe"),
            extract_hazard_id(incident.get("hazard")),
            incident.get("incidentOn"),
            incident.get("reportedOn"),
            incident.get("verified"),
            incident.get("approved"),
            incident.get("source"),
            incident.get("dataSource"),
            point_wkt,
            extract_loss_id(incident.get("loss")),
            incident.get("createdOn"),
            incident.get("modifiedOn"),
            psycopg2.extras.Json(incident),
        ),
    )


def run_ingestion(days_back: int = 30):
    params = build_initial_params(days_back)
    url = BASE_URL
    conn = get_db_connection()
    cur = conn.cursor()

    total_inserted = 0
    page_num = 1

    while url:
        logger.info(f"Fetching page {page_num}...")
        data = fetch_page(url, params=params)
        results = data.get("results", [])

        if not results:
            logger.info(f"Page {page_num} returned 0 results — reached end of data. Stopping.")
            break

        for incident in results:
            try:
                upsert_incident(cur, incident)
                total_inserted += 1
            except Exception as e:
                logger.error(f"Failed to upsert incident {incident.get('id')}: {e}")
                conn.rollback()
                continue

        conn.commit()
        logger.info(f"Page {page_num}: upserted {len(results)} incidents "
                    f"(running total: {total_inserted})")

        url = data.get("next")
        params = None
        page_num += 1

        if url:
            time.sleep(1 + random.uniform(0, 0.5))

    cur.close()
    conn.close()
    logger.info(f"Ingestion complete. Total incidents upserted: {total_inserted}")


if __name__ == "__main__":
    run_ingestion(days_back=3)