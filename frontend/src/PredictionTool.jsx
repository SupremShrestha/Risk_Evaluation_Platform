import { useEffect, useState } from "react";
import {
  MONTHS, MONTHS_SHORT, HAZARD_COLORS, TRAINED_HAZARDS,
  SEASONAL_INTENSITY, API_BASE,
} from "./constants";

function PredictionTool() {
  const [districts, setDistricts] = useState([]);
  const [district, setDistrict] = useState("");
  const [hazard, setHazard] = useState(TRAINED_HAZARDS[0]);
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/districts/`)
      .then((res) => res.json())
      .then((data) => {
        setDistricts(data);
        if (data.length) setDistrict(data[0].title);
      });
  }, []);

  const handlePredict = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/predict/`, {
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
    if (count < 2) return { label: "Low", color: "var(--ok)" };
    if (count < 6) return { label: "Moderate", color: "#a3760f" };
    return { label: "High", color: "var(--danger)" };
  };

  const hazardColor = HAZARD_COLORS[hazard] || "var(--ink)";
  const maxIntensity = Math.max(...SEASONAL_INTENSITY);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Risk Predictor</h1>
        <p className="page-desc">
          Expected incident count for a given district, hazard, and month —
          based on historical seasonal patterns and recent trends.
        </p>
      </div>

      <div className="panel">
        <div className="field-row">
          <div className="field">
            <label className="field-label">District</label>
            <select value={district} onChange={(e) => setDistrict(e.target.value)}>
              {districts.map((d) => (
                <option key={d.id} value={d.title}>{d.title}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field-label">Hazard</label>
            <select value={hazard} onChange={(e) => setHazard(e.target.value)}>
              {TRAINED_HAZARDS.map((h) => (
                <option key={h} value={h}>{h}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field-label">Month</label>
            <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
              {MONTHS.map((m, i) => (
                <option key={i} value={i + 1}>{m}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label className="field-label">Year</label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </div>

          <button className="btn-primary" onClick={handlePredict} disabled={loading}>
            {loading ? "Predicting…" : "Predict Risk"}
          </button>
        </div>

        <div className="season-strip">
          <div className="season-strip-label">Typical seasonal pattern — {hazard}</div>
          <div className="season-strip-bars">
            {MONTHS_SHORT.map((label, i) => {
              const isSelected = i + 1 === month;
              const heightPct = Math.max(8, (SEASONAL_INTENSITY[i] / maxIntensity) * 100);
              return (
                <div className="season-bar-wrap" key={i}>
                  <div
                    className={`season-bar${isSelected ? " selected" : ""}`}
                    style={{ height: `${heightPct}%`, "--hazard-color": hazardColor }}
                  />
                  <span className={`season-bar-month${isSelected ? " selected" : ""}`}>{label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="contour-rule" />

      {error && <div className="error-banner">{error}</div>}

      {result && (
        <div
          className="result-card"
          style={{ "--hazard-color": hazardColor }}
        >
          <div className="result-heading">{result.district} · {result.hazard}</div>
          <div className="mono" style={{ fontSize: "0.8rem", marginBottom: 2 }}>
            {MONTHS[result.month - 1]} {result.year}
          </div>
          <div className="result-count">{result.predicted_incident_count}</div>
          <div className="result-count-label">incidents predicted</div>
          <span
            className="risk-pill"
            style={{ "--pill-color": riskLevel(result.predicted_incident_count).color }}
          >
            {riskLevel(result.predicted_incident_count).label} risk
          </span>
          <div className="result-detail">
            Based on {result.features_used.prev_month_count} incidents last month ·
            historical average of {result.features_used.historical_month_avg} for this month
          </div>
        </div>
      )}
    </div>
  );
}

export default PredictionTool;
