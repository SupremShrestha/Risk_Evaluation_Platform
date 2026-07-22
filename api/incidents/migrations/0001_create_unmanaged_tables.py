from django.db import migrations


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS districts (
                    id          INTEGER PRIMARY KEY,
                    title       TEXT NOT NULL,
                    title_ne    TEXT,
                    code        TEXT,
                    province_id INTEGER
                );

                CREATE TABLE IF NOT EXISTS hazards (
                    id          INTEGER PRIMARY KEY,
                    title       TEXT NOT NULL,
                    title_ne    TEXT,
                    type        TEXT,
                    color       TEXT,
                    icon_url    TEXT
                );

                CREATE EXTENSION IF NOT EXISTS postgis;

                CREATE TABLE IF NOT EXISTS incidents (
                    id              INTEGER PRIMARY KEY,
                    title           TEXT,
                    title_ne        TEXT,
                    hazard_id       INTEGER,
                    incident_on     TIMESTAMPTZ,
                    reported_on     TIMESTAMPTZ,
                    verified        BOOLEAN,
                    approved        BOOLEAN,
                    source          TEXT,
                    data_source     TEXT,
                    point           GEOMETRY(Point, 4326),
                    loss_id         INTEGER,
                    district_id     INTEGER,
                    created_on      TIMESTAMPTZ,
                    modified_on     TIMESTAMPTZ,
                    raw_data        JSONB NOT NULL,
                    ingested_at     TIMESTAMPTZ DEFAULT now()
                );
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS incidents;
                DROP TABLE IF EXISTS hazards;
                DROP TABLE IF EXISTS districts;
            """,
        ),
    ]