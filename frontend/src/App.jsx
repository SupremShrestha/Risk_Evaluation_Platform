import { useState } from "react";
import IncidentsTable from "./IncidentsTable";
import PredictionTool from "./PredictionTool";

function App() {
  const [activeTab, setActiveTab] = useState("predict");

  const tabStyle = (tab) => ({
    padding: "0.6rem 1.2rem",
    cursor: "pointer",
    border: "none",
    borderBottom: activeTab === tab ? "3px solid #2563eb" : "3px solid transparent",
    background: "none",
    fontSize: "1rem",
    fontWeight: activeTab === tab ? "600" : "400",
    color: activeTab === tab ? "#111" : "#666",
  });

  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: "1100px", margin: "0 auto", padding: "1rem" }}>
      <h1>BIPAD Risk Platform</h1>
      <div style={{ borderBottom: "1px solid #ddd", marginBottom: "1.5rem" }}>
        <button style={tabStyle("predict")} onClick={() => setActiveTab("predict")}>
          Risk Predictor
        </button>
        <button style={tabStyle("incidents")} onClick={() => setActiveTab("incidents")}>
          Recent Incidents
        </button>
      </div>

      {activeTab === "predict" && <PredictionTool />}
      {activeTab === "incidents" && <IncidentsTable />}
    </div>
  );
}

export default App;