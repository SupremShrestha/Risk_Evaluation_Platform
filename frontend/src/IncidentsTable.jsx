import { useEffect, useState } from "react";

function IncidentsTable() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/incidents/")
      .then((res) => res.json())
      .then((data) => {
        setIncidents(data.results);
        setLoading(false);
      });
  }, []);

  if (loading) return <p>Loading incidents...</p>;

  return (
    <div>
      <p>Showing {incidents.length} most recent incidents</p>
      <table border="1" cellPadding="8" style={{ borderCollapse: "collapse", width: "100%" }}>
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
              <td style={{ color: inc.hazard?.color }}>{inc.hazard?.title}</td>
              <td>{new Date(inc.incident_on).toLocaleDateString()}</td>
              <td>{inc.verified ? "✅" : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default IncidentsTable;
