import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";

const NEPAL_CENTER = [28.3949, 84.1240];

function IncidentMap() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/incidents/map/")
      .then((res) => res.json())
      .then((data) => {
        setIncidents(data);  // no .results — this endpoint isn't paginated
        setLoading(false);
      });
  }, []);

  if (loading) return <p>Loading map...</p>;

  return (
    <div>
      <p>Showing {incidents.length} most recent incidents on the map</p>
      <MapContainer
        center={NEPAL_CENTER}
        zoom={7}
        style={{ height: "600px", width: "100%", borderRadius: "8px" }}
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
    </div>
  );
}

export default IncidentMap;