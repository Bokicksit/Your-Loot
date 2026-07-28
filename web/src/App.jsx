import { useEffect, useState } from "react";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api.js";
import { Icon, IconDefs } from "./components/Icons.jsx";
import HomePage from "./pages/HomePage.jsx";
import CardsPage from "./pages/CardsPage.jsx";
import PokedexPage from "./pages/PokedexPage.jsx";
import WantedPage from "./pages/WantedPage.jsx";
import GamesPage from "./pages/GamesPage.jsx";
import HardwarePage from "./pages/HardwarePage.jsx";
import MoviesPage from "./pages/MoviesPage.jsx";

const TABS = [
  { to: "/cards", icon: "card", label: "Cards" },
  { to: "/pokedex", icon: "ball", label: "Pokédex" },
  { to: "/wanted", icon: "star", label: "Wanted" },
  { to: "/games", icon: "pad", label: "Games" },
  { to: "/hardware", icon: "console", label: "Hardware" },
  { to: "/movies", icon: "disc", label: "Movies" },
];

export default function App() {
  // undefined = loading, null = never set (first run), "" = skipped, "Bo" = set
  const [ownerName, setOwnerName] = useState(undefined);
  const [nameDraft, setNameDraft] = useState("");

  useEffect(() => {
    api.settings().then((s) => setOwnerName(s.owner_name)).catch(() => setOwnerName(""));
  }, []);

  const saveName = async (name) => {
    const saved = await api.saveSettings({ owner_name: name });
    setOwnerName(saved.owner_name);
  };

  return (
    <BrowserRouter>
      <IconDefs />
      <header className="topbar">
        {/* brand doubles as the way home */}
        <Link to="/" className="brand-link">
          <h1 className="brand">
            <Icon id="coin" />
            {ownerName ? `${ownerName}’s` : "Your"} <em>Loot</em>
          </h1>
        </Link>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/cards" element={<CardsPage />} />
          <Route path="/pokedex" element={<PokedexPage />} />
          <Route path="/wanted" element={<WantedPage />} />
          <Route path="/games" element={<GamesPage />} />
          <Route path="/hardware" element={<HardwarePage />} />
          <Route path="/movies" element={<MoviesPage />} />
        </Routes>
      </main>
      {/* bottom tab bar — thumb-reachable, floats as a pill on desktop */}
      <nav className="tabbar">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to}>
            <Icon id={t.icon} />
            <span>{t.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* first run: personalize the vault */}
      {ownerName === null && (
        <div className="modal-scrim">
          <form
            className="modal"
            onSubmit={(e) => {
              e.preventDefault();
              saveName(nameDraft.trim());
            }}
          >
            <span className="glyph"><Icon id="coin" /></span>
            <h2>Whose loot is this?</h2>
            <p>Your name goes on the vault door. You can leave it blank.</p>
            <input
              type="text"
              maxLength={50}
              autoFocus
              placeholder="Collector name"
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
            />
            <button type="submit" className="primary">
              {nameDraft.trim() ? `Make it ${nameDraft.trim()}’s Loot` : "Keep it “Your Loot”"}
            </button>
          </form>
        </div>
      )}
    </BrowserRouter>
  );
}
