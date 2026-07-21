import os
import requests
import psycopg2
from dotenv import load_dotenv
import time

load_dotenv("../docker/.env")

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5433,
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_all(url):
    """Paginate through a reference endpoint and return every result."""
    results = []
    while url:
        for attempt in range(3):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                print(f"Request failed (attempt {attempt + 1}/3): {e}")
                if attempt == 2:
                    raise
                time.sleep(2)

        data = response.json()
        page_results = data.get("results", [])

        if not page_results:
            print("Received empty page — reached end of data. Stopping.")
            break

        results.extend(page_results)
        url = data.get("next")
        print(f"Fetched {len(results)} so far...")

    return results

def load_districts(cur):
    districts = fetch_all("https://bipadportal.gov.np/api/v1/district/?limit=20")
    for d in districts:
        cur.execute(
            """
            INSERT INTO districts (id, title, title_ne, code, province_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;
            """,
            (d["id"], d["title"], d.get("title_ne"), d.get("code"), d.get("province")),
        )
    print(f"Loaded {len(districts)} districts.")

def load_municipalities(cur):
    municipalities = fetch_all("https://bipadportal.gov.np/api/v1/municipality/?limit=20")
    for m in municipalities:
        cur.execute(
            """
            INSERT INTO municipalities (id, title, title_ne, type, code, district_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;
            """,
            (m["id"], m["title"], m.get("title_ne"), m.get("type"), m.get("code"), m.get("district")),
        )
    print(f"Loaded {len(municipalities)} municipalities.")

if __name__ == "__main__":
    conn = get_db_connection()
    cur = conn.cursor()
    load_districts(cur)      # districts first — municipalities FK-reference them
    load_municipalities(cur)
    conn.commit()
    cur.close()
    conn.close()