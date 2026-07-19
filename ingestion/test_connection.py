import os
import requests
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv("../docker/.env")

BIPAD_URL = (
    "https://bipadportal.gov.np/api/v1/incident/"
    "?limit=1&ordering=-incident_on&data_source=drr_api"
)

def fetch_one_incident():
    response = requests.get(BIPAD_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data["results"][0]

def extract_loss_id(loss):
    """loss can be either a plain integer ID, a full nested object, or None."""
    if loss is None:
        return None
    if isinstance(loss, dict):
        return loss.get("id")
    return loss  # already just an int

def insert_incident(incident):
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    cur = conn.cursor()

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
            modified_on = EXCLUDED.modified_on,
            raw_data = EXCLUDED.raw_data;
        """,
        (
            incident["id"],
            incident.get("title"),
            incident.get("titleNe"),
            incident.get("hazard"),
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
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    incident = fetch_one_incident()
    print(f"Fetched incident #{incident['id']}: {incident['title']}")
    insert_incident(incident)
    print("Inserted successfully.")