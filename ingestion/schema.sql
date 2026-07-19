CREATE TABLE IF NOT EXISTS incidents (
    id              INTEGER PRIMARY KEY,       -- BIPAD's own incident ID (our upsert key)
    title           TEXT,
    title_ne        TEXT,
    hazard_id       INTEGER,
    incident_on     TIMESTAMPTZ,
    reported_on     TIMESTAMPTZ,
    verified        BOOLEAN,
    approved        BOOLEAN,
    source          TEXT,
    data_source     TEXT,
    point           GEOMETRY(Point, 4326),      -- 4326 = standard lat/lng (WGS84)
    loss_id         INTEGER,
    created_on      TIMESTAMPTZ,
    modified_on     TIMESTAMPTZ,
    raw_data        JSONB NOT NULL,             -- full original API response, our safety net
    ingested_at     TIMESTAMPTZ DEFAULT now()   -- when WE pulled it, not BIPAD's timestamp
);

CREATE INDEX IF NOT EXISTS idx_incidents_hazard ON incidents(hazard_id);
CREATE INDEX IF NOT EXISTS idx_incidents_incident_on ON incidents(incident_on);
CREATE INDEX IF NOT EXISTS idx_incidents_point ON incidents USING GIST(point);