import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import { API_BASE } from "./constants";

const NEPAL_CENTER = [28.3949, 84.124];

function IncidentMap() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/incidents/map/`)
      .then((res) => res.json())
      .then((data) => {
        setIncidents(data); // no .results — this endpoint isn't paginated
        setLoading(false);
      });
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
          <div className="status-line">{incidents.length} most recent incidents on the map</div>

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
          </MapContainer>
        </>
      )}
    </div>
  );
}

export default IncidentMap;
