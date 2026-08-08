export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export const MONTHS_SHORT = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

// Each trained hazard gets its own earth-derived color, used consistently
// across the predictor, table, and map — rather than one generic accent color.
export const HAZARD_COLORS = {
  Landslide: "var(--hazard-landslide)",
  Flood: "var(--hazard-flood)",
  Fire: "var(--hazard-fire)",
  "Snake Bite": "var(--hazard-snakebite)",
};

export const HAZARD_COLORS_HEX = {
  Landslide: "#8b5e34",
  Flood: "#2a6f97",
  Fire: "#c1440e",
  "Snake Bite": "#5b7b3b",
};

export const TRAINED_HAZARDS = ["Landslide", "Snake Bite", "Fire", "Flood"];

// Illustrative relative seasonal intensity (Jan=1 ... Dec=12), reflecting the
// monsoon-driven swing described in the README (~40x quiet-to-peak for
// landslides). Not model output — a visual cue, same spirit as riskLevel().
export const SEASONAL_INTENSITY = [4, 3, 4, 6, 10, 55, 100, 90, 45, 12, 5, 4];

export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
