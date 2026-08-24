import { useEffect, useState } from "react";
import { API_BASE } from "./constants";

function HazardPredictor() {
  const [districts, setDistricts] = useState([]);
  const [district, setDistrict] = useState("");
  const [date, setDate] = useState("2026-07-05");
  // Defaults to a known-good backfilled date rather than "N days ago" --
  // district_daily_rainfall currently only has sparse manually-backfilled
  // history (see known-issues.md), not a continuous daily record, since
  // the Airflow DAG hasn't been run continuously in this environment.
  // A relative offset would drift onto un-backfilled dates over time.
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
      const res = await fetch(`${API_BASE}/api/v1/predict-hazard/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ district, date }),
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

  // Thresholds are illustrative, not model-calibrated cutoffs -- same
  // spirit as PredictionTool's riskLevel(), just for a probability instead
  // of a count.
  const riskLevel = (probability) => {
    if (probability < 0.3) return { label: "Low", color: "var(--ok)" };
    if (probability < 0.6) return { label: "Moderate", color: "#a3760f" };
    return { label: "High", color: "var(--danger)" };
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Hazard Risk (Rainfall Lead-Lag)</h1>
        <p className="page-desc">
          Probability of a hazard incident on a given day, driven by recent
          rainfall (CHIRPS) and district-level baseline risk — a same/near-term
          signal, distinct from the monthly count predictor.
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
            <label className="field-label">Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>

          <button className="btn-primary" onClick={handlePredict} disabled={loading}>
            {loading ? "Predicting…" : "Predict Risk"}
          </button>
        </div>
      </div>

      <div className="contour-rule" />

      {error && (
        <div className="error-banner">
          {error}
          {error.includes("No rainfall data") && (
            <div style={{ marginTop: 4, fontSize: "0.85rem" }}>
              CHIRPS rainfall data typically lags a few weeks behind today —
              try a date further in the past.
            </div>
          )}
        </div>
      )}

      {result && (
        <div className="result-card" style={{ "--hazard-color": "var(--hazard-flood)" }}>
          <div className="result-heading">{result.district}</div>
          <div className="mono" style={{ fontSize: "0.8rem", marginBottom: 2 }}>
            {result.date}
          </div>
          <div className="result-count">{Math.round(result.risk_probability * 100)}%</div>
          <div className="result-count-label">estimated risk probability</div>
          <span
            className="risk-pill"
            style={{ "--pill-color": riskLevel(result.risk_probability).color }}
          >
            {riskLevel(result.risk_probability).label} risk
          </span>
          <div className="result-detail">
            Rainfall: {result.features_used.rain_1d}mm (1d) ·{" "}
            {result.features_used.rain_3d}mm (3d) ·{" "}
            {result.features_used.rain_7d}mm (7d) ·{" "}
            peak {result.features_used.rain_peak_7d}mm
          </div>
          <div className="result-detail" style={{ marginTop: 6, opacity: 0.75 }}>
            {result.note}
          </div>
        </div>
      )}
    </div>
  );
}

export default HazardPredictor;
