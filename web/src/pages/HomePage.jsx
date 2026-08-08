import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { MODULES, useEnabledModules, useSettings } from "../settings.jsx";

const PATHS = {
  cards: "/cards", games: "/games", hardware: "/hardware",
  movies: "/movies", books: "/books", records: "/records",
  lego: "/lego", comics: "/comics",
};
const UNIT = {
  cards: "card", games: "title", hardware: "item", movies: "disc", books: "book",
  records: "record", lego: "set", comics: "issue",
};

export default function HomePage() {
  const { settings } = useSettings();
  const enabled = useEnabledModules();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
  }, []);

  // On or off, and nothing in between. Starring used to be a second, quieter
  // switch that decided the same thing, which meant a collection could be
  // turned on and still be nowhere — so it's gone, and this list is simply
  // what Settings says you collect.
  const shown = enabled;
  const hidden = MODULES.length - enabled.length;
  // Hardware used to borrow the games count, because the API had no hardware
  // number to give — so a shelf with one console read "29 items". It reports
  // both separately now, and this asks for what it means.
  const count = (key) => (stats?.[key] ? stats[key].items : null);

  return (
    <div className="home">
      <h2>What are we opening?</h2>

      <div className="home-tiles">
        {shown.map((m) => (
          <Link key={m.key} to={PATHS[m.key]} className="home-tile">
            <Icon id={m.icon} />
            <strong>{m.label}</strong>
            {count(m.key) != null && (
              <small>
                {count(m.key)} {UNIT[m.key]}
                {count(m.key) === 1 ? "" : "s"}
              </small>
            )}
          </Link>
        ))}

      </div>

      {/* Only worth saying when something is actually missing. A line telling
          you about collections you already have is noise on every visit. */}
      {hidden > 0 && (
        <p className="home-hint">
          <Icon id="sliders" />
          <span>
            {hidden} more {hidden === 1 ? "collection" : "collections"} to turn
            on in <Link to="/settings">Settings</Link>.
          </span>
        </p>
      )}

      {shown.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="sliders" /></span>
          <strong>No collections turned on</strong>
          <p>Pick what you collect and it'll show up here.</p>
          <Link to="/settings" className="primary">Open settings</Link>
        </div>
      )}
    </div>
  );
}
