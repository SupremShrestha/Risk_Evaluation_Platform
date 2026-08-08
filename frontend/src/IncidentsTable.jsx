import { useEffect, useState } from "react";
import { API_BASE } from "./constants";

function IncidentsTable() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/incidents/`)
      .then((res) => res.json())
      .then((data) => {
        setIncidents(data.results);
        setLoading(false);
      });
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Recent Incidents</h1>
        <p className="page-desc">
          Latest verified and unverified incident reports ingested from the BIPAD Portal.
        </p>
      </div>

      {loading ? (
        <p className="status-line">Loading incidents…</p>
      ) : (
        <>
          <div className="status-line">{incidents.length} most recent incidents</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Hazard</th>
                <th>Date</th>
                <th>Verified</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.id}>
                  <td>{inc.title}</td>
                  <td>
                    <span className="hazard-chip">
                      <span className="hazard-dot" style={{ background: inc.hazard?.color || "#999" }} />
                      {inc.hazard?.title}
                    </span>
                  </td>
                  <td className="mono">{new Date(inc.incident_on).toLocaleDateString()}</td>
                  <td>{inc.verified ? "✓" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

export default IncidentsTable;
