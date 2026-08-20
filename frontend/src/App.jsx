import { useState } from "react";
import IncidentsTable from "./IncidentsTable";
import PredictionTool from "./PredictionTool";
import HazardPredictor from "./HazardPredictor";
import IncidentMap from "./IncidentMap";
import { MONTHS } from "./constants";

const TABS = [
  { key: "predict", label: "Risk Predictor" },
  { key: "hazard", label: "Hazard Risk (Rainfall)" },
  { key: "incidents", label: "Recent Incidents" },
  { key: "map", label: "Map View" },
];

function currentSeasonNote() {
  const month = new Date().getMonth() + 1; // 1-12
  const inMonsoon = month >= 6 && month <= 9;
  return {
    month: MONTHS[month - 1],
    note: inMonsoon ? "Monsoon — peak landslide risk" : "Outside monsoon window",
  };
}

function App() {
  const [activeTab, setActiveTab] = useState("predict");
  const season = currentSeasonNote();

  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="rail-mark">BIPAD Risk<br />Platform</div>
        <div className="rail-subtitle">Nepal · NDRRMA data</div>

        <nav className="rail-nav">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              className={`rail-nav-item${activeTab === tab.key ? " active" : ""}`}
              onClick={() => setActiveTab(tab.key)}
            >
              <span className="rail-nav-dot" />
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="rail-footer">
          <div className="rail-footer-label">Current period</div>
          <div className="rail-footer-value">{season.month}</div>
          <div className="rail-footer-label" style={{ marginTop: 8 }}>{season.note}</div>
        </div>
      </aside>

      <main className="main">
        {activeTab === "predict" && <PredictionTool />}
        {activeTab === "hazard" && <HazardPredictor />}
        {activeTab === "incidents" && <IncidentsTable />}
        {activeTab === "map" && <IncidentMap />}
      </main>
    </div>
  );
}

export default App;
