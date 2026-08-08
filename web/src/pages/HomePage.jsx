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

  const favs = settings?.favorite_modules || [];
  // Starred first — but with the full list gone from the tab bar, this page is
  // the only way into a collection, so an unstarred one would be stranded.
  // Nothing starred means everything you've turned on.
  const starred = enabled.filter((m) => favs.includes(m.key));
  const shown = starred.length ? starred : enabled;
  // Two different kinds of missing, and telling someone to "turn on" a
  // collection they already turned on is the sort of small wrongness that
  // makes people stop trusting the rest of the copy.
  const off = MODULES.length - enabled.length;
  const unstarred = enabled.length - shown.length;
  const hidden = off + unstarred;
  const count = (key) => {
    // hardware lives in the games module server-side
    const s = stats?.[key === "hardware" ? "games" : key];
    return s ? s.items : null;
  };

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
            {hidden} more {hidden === 1 ? "collection" : "collections"}{" "}
            {off && unstarred
              ? "to turn on or star"
              : off
                ? `to turn on`
                : `to star`}{" "}
            in <Link to="/settings">Settings</Link>.
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
