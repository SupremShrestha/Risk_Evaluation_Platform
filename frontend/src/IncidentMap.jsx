import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import { API_BASE } from "./constants";

const NEPAL_CENTER = [28.3949, 84.124];

// Scales a cluster's incident count to a marker radius -- sqrt so that
// area (not just radius) grows roughly proportionally with size, which is
// the perceptually correct way to size circles by magnitude.
function hotspotRadius(size) {
  return Math.max(8, Math.min(30, Math.sqrt(size) * 2.5));
}

function IncidentMap() {
  const [incidents, setIncidents] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showHotspots, setShowHotspots] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/incidents/map/`)
      .then((res) => res.json())
      .then((data) => {
        setIncidents(data); // no .results — this endpoint isn't paginated
        setLoading(false);
      });

    fetch(`${API_BASE}/api/v1/hotspots/`)
      .then((res) => res.json())
      .then((data) => setHotspots(data));
  }, []);

  const legend = useMemo(() => {
    const seen = new Map();
    incidents.forEach((inc) => {
      if (inc.hazard_title && inc.hazard_color && !seen.has(inc.hazard_title)) {
        seen.set(inc.hazard_title, inc.hazard_color);
      }
    });
    return Array.from(seen.entries());
  }, [incidents]);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Map View</h1>
        <p className="page-desc">
          Geolocated incidents across Nepal, clustered by proximity.
        </p>
      </div>

      {loading ? (
        <p className="status-line">Loading map…</p>
      ) : (
        <>
          <div className="status-line" style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span>{incidents.length} most recent incidents on the map</span>
            <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={showHotspots}
                onChange={(e) => setShowHotspots(e.target.checked)}
              />
              Show hotspot clusters ({hotspots.length})
            </label>
          </div>

          {legend.length > 0 && (
            <div className="map-legend">
              {legend.map(([title, color]) => (
                <span className="map-legend-item" key={title}>
                  <span className="hazard-dot" style={{ background: color }} />
                  {title}
                </span>
              ))}
            </div>
          )}

          {showHotspots && (
            <div className="status-line" style={{ fontSize: "0.85rem", opacity: 0.75, marginTop: -4 }}>
              Larger circles = more incidents in that data-driven hotspot (DBSCAN clustering on
              actual incident locations, computed weekly — not the same as the proximity clustering above).
            </div>
          )}

          <MapContainer
            center={NEPAL_CENTER}
            zoom={7}
            style={{ height: "600px", width: "100%", borderRadius: "6px", border: "1px solid var(--line-soft)" }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <MarkerClusterGroup chunkedLoading>
              {incidents
                .filter((inc) => inc.latitude && inc.longitude)
                .map((inc) => (
                  <CircleMarker
                    key={inc.id}
                    center={[inc.latitude, inc.longitude]}
                    radius={6}
                    pathOptions={{
                      color: inc.hazard_color || "#666",
                      fillColor: inc.hazard_color || "#666",
                      fillOpacity: 0.7,
                    }}
                  >
                    <Popup>
                      <strong>{inc.hazard_title}</strong>
                      <br />
                      {new Date(inc.incident_on).toLocaleDateString()}
                    </Popup>
                  </CircleMarker>
                ))}
            </MarkerClusterGroup>

            {showHotspots &&
              hotspots.map((h) => (
                <CircleMarker
                  key={h.id}
                  center={[h.center_lat, h.center_lon]}
                  radius={hotspotRadius(h.size)}
                  pathOptions={{
                    color: h.hazard_color || "#666",
                    fillColor: h.hazard_color || "#666",
                    fillOpacity: 0.2,
                    weight: 2,
                    dashArray: "4",
                  }}
                >
                  <Popup>
                    <strong>{h.hazard_title} hotspot</strong>
                    <br />
                    {h.size} incidents
                    <br />
                    Near {h.dominant_district_title}
                  </Popup>
                </CircleMarker>
              ))}
          </MapContainer>
        </>
      )}
    </div>
  );
}

export default IncidentMap;
