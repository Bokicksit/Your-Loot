import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { useEnabledModules, useSettings } from "../settings.jsx";

const PATHS = {
  cards: "/cards", games: "/games", hardware: "/hardware",
  movies: "/movies", books: "/books", records: "/records",
  lego: "/lego", comics: "/comics",
};
const UNIT = {
  cards: "card", games: "title", hardware: "item", movies: "disc", books: "book",
  records: "record", lego: "set", comics: "issue",
};

export default function HomePage({ onOpenCollections }) {
  const { settings } = useSettings();
  const enabled = useEnabledModules();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
  }, []);

  const favs = settings?.favorite_modules || [];
  // this tab is the starred shortcuts and nothing else — the full list is one
  // tap away on Collections, so there's no "see all" to duplicate it
  const shown = enabled.filter((m) => favs.includes(m.key));
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
          <Icon id="target" />
          <strong>Wanted</strong>
          {wanted > 0 && <small>{wanted} on the hunt</small>}
        </Link>
      </div>

      {/* nothing starred yet — say what this tab is for rather than sit empty */}
      {shown.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="star" /></span>
          <strong>No favourites yet</strong>
          <p>
            Star the collections you reach for most and they'll live here. Everything
            else stays one tap away under Collections.
          </p>
          <button className="ghost" onClick={onOpenCollections}>
            <Icon id="card" />
            Browse collections
          </button>
        </div>
      )}
    </div>
  );
}
