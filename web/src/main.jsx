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

// Registered after paint so it never delays the first render, and only where
// the browser will honour it — service workers need a secure origin, which a
// LAN install over plain http isn't. There it simply doesn't register, and the
// app carries on as an ordinary page.
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* an offline shell is a bonus; never let it break the app */
    });
  });
}
