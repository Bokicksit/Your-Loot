import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
// Space Grotesk bundled locally (@fontsource) — no CDN, works offline
import "@fontsource/space-grotesk/400.css";
import "@fontsource/space-grotesk/500.css";
import "@fontsource/space-grotesk/700.css";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
