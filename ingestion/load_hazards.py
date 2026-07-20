import os
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv("../docker/.env")

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5433,
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

def load_hazards():
    response = requests.get("https://bipadportal.gov.np/api/v1/hazard/?limit=1000", timeout=10)
    response.raise_for_status()
    hazards = response.json()["results"]

    conn = get_db_connection()
    cur = conn.cursor()

    for h in hazards:
        cur.execute(
            """
            INSERT INTO hazards (id, title, title_ne, type, color, icon_url)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                type = EXCLUDED.type;
            """,
            (h["id"], h["title"], h.get("titleNe"), h.get("type"), h.get("color"), h.get("icon")),
        )

    conn.commit()
    cur.close()
    conn.close()
    print(f"Loaded {len(hazards)} hazards.")

if __name__ == "__main__":
    load_hazards()