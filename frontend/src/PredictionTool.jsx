import { useEffect, useState } from "react";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function PredictionTool() {
  const [districts, setDistricts] = useState([]);
  const [hazards, setHazards] = useState([]);
  const [district, setDistrict] = useState("");
  const [hazard, setHazard] = useState("");
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const TRAINED_HAZARDS = ["Landslide", "Snake Bite", "Fire", "Flood"];

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/districts/")
      .then((res) => res.json())
      .then((data) => {
        setDistricts(data);
        if (data.length) setDistrict(data[0].title);
      });

    setHazards(TRAINED_HAZARDS.map((title, id) => ({ id, title })));
    setHazard(TRAINED_HAZARDS[0]);
  }, []);

  const handlePredict = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/predict/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ district, hazard, year, month }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Prediction failed");
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const riskLevel = (count) => {
    if (count < 2) return { label: "Low", color: "#16a34a" };
    if (count < 6) return { label: "Moderate", color: "#d97706" };
    return { label: "High", color: "#dc2626" };
  };

  return (
    <div>
      <p style={{ color: "#555" }}>
        Predicted incident count for a given district, hazard, and month — based on
        historical seasonal patterns and recent trends.
      </p>

      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
        <label>
          District<br />
          <select value={district} onChange={(e) => setDistrict(e.target.value)}>
            {districts.map((d) => (
              <option key={d.id} value={d.title}>{d.title}</option>
            ))}
          </select>
        </label>

        <label>
          Hazard<br />
          <select value={hazard} onChange={(e) => setHazard(e.target.value)}>
            {hazards.map((h) => (
              <option key={h.id} value={h.title}>{h.title}</option>
            ))}
          </select>
        </label>

        <label>
          Month<br />
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTHS.map((m, i) => (
              <option key={i} value={i + 1}>{m}</option>
            ))}
          </select>
        </label>

        <label>
          Year<br />
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={{ width: "80px" }}
          />
        </label>

        <button onClick={handlePredict} disabled={loading} style={{ alignSelf: "flex-end", padding: "0.4rem 1rem" }}>
          {loading ? "Predicting..." : "Predict Risk"}
        </button>
      </div>

      {error && <p style={{ color: "#dc2626" }}>Error: {error}</p>}

      {result && (
        <div style={{ border: "1px solid #ddd", borderRadius: "8px", padding: "1.5rem", maxWidth: "500px" }}>
          <h3>{result.district} — {result.hazard}</h3>
          <p>{MONTHS[result.month - 1]} {result.year}</p>
          <p style={{ fontSize: "2rem", fontWeight: "bold", color: riskLevel(result.predicted_incident_count).color }}>
            {result.predicted_incident_count} incidents predicted
          </p>
          <p style={{ color: riskLevel(result.predicted_incident_count).color, fontWeight: "600" }}>
            Risk level: {riskLevel(result.predicted_incident_count).label}
          </p>
          <hr />
          <p style={{ fontSize: "0.85rem", color: "#666" }}>
            Based on: {result.features_used.prev_month_count} incidents last month,
            historical average of {result.features_used.historical_month_avg} for this month
          </p>
        </div>
      )}
    </div>
  );
}

export default PredictionTool;
