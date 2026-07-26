import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

// Splash: pick a collection. Tab bar still works everywhere; this is just the
// front door instead of dumping straight into cards.
export default function HomePage() {
  const [stats, setStats] = useState(null);
  const [version, setVersion] = useState("");

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
    api.health().then((h) => setVersion(h.version)).catch(() => {});
  }, []);

  const totalWanted = stats
    ? Object.values(stats).reduce((a, s) => a + s.wanted, 0)
    : 0;

  return (
    <div className="home">
      <h2>What are we opening?</h2>
      <div className="home-tiles">
        <Link to="/cards" className="home-tile">
          <Icon id="card" />
          <strong>Cards</strong>
        </Link>
        <Link to="/games" className="home-tile">
          <Icon id="pad" />
          <strong>Games</strong>
        </Link>
        <Link to="/movies" className="home-tile">
          <Icon id="disc" />
          <strong>Movies</strong>
        </Link>
        <Link to="/wanted" className="home-tile">
          <Icon id="star" />
          <strong>Wanted</strong>
          {stats && totalWanted > 0 && <small>{totalWanted} on the hunt</small>}
        </Link>
      </div>
      {version && <p className="version-tag">v{version}</p>}
    </div>
  );
}
