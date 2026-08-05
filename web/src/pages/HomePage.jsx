import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { useEnabledModules, useSettings } from "../settings.jsx";

const PATHS = {
  cards: "/cards", games: "/games", hardware: "/hardware",
  movies: "/movies", books: "/books",
};
const UNIT = {
  cards: "card", games: "title", hardware: "item", movies: "disc", books: "book",
};

export default function HomePage({ onOpenCollections }) {
  const { settings } = useSettings();
  const enabled = useEnabledModules();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
  }, []);

  const favs = settings?.favorite_modules || [];
  // favourites are the fast path; if none are starred, show everything so
  // Home is never an empty screen
  const shown = favs.length ? enabled.filter((m) => favs.includes(m.key)) : enabled;
  const wanted = stats
    ? Object.values(stats).reduce((a, s) => a + s.wanted, 0)
    : 0;

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

        <Link to="/wanted" className="home-tile">
          <Icon id="star" />
          <strong>Wanted</strong>
          {wanted > 0 && <small>{wanted} on the hunt</small>}
        </Link>
      </div>

      {favs.length > 0 && enabled.length > shown.length && (
        <button className="ghost home-more" onClick={onOpenCollections}>
          <Icon id="sliders" />
          All collections
        </button>
      )}
    </div>
  );
}
