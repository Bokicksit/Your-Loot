import { useState } from "react";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Icon, IconDefs } from "./components/Icons.jsx";
import Onboarding from "./components/Onboarding.jsx";
import { MODULES, SettingsProvider, useEnabledModules, useSettings } from "./settings.jsx";
import HomePage from "./pages/HomePage.jsx";
import CardsPage from "./pages/CardsPage.jsx";
import WantedPage from "./pages/WantedPage.jsx";
import GamesPage from "./pages/GamesPage.jsx";
import HardwarePage from "./pages/HardwarePage.jsx";
import MoviesPage from "./pages/MoviesPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";

const PATHS = {
  cards: "/cards",
  games: "/games",
  hardware: "/hardware",
  movies: "/movies",
};

// Bottom bar is deliberately three items — the individual collections live
// behind the Collections sheet, with favourites surfaced on Home.
function TabBar({ onOpenCollections }) {
  const { pathname } = useLocation();
  const inCollection = Object.values(PATHS).some((p) => pathname.startsWith(p));
  return (
    <nav className="tabbar">
      <NavLink to="/" end>
        <Icon id="coin" />
        <span>Home</span>
      </NavLink>
      <button
        className={inCollection ? "active" : ""}
        onClick={onOpenCollections}
        aria-haspopup="menu"
      >
        <Icon id="card" />
        <span>Collections</span>
      </button>
      <NavLink to="/wanted">
        <Icon id="star" />
        <span>Wanted</span>
      </NavLink>
    </nav>
  );
}

function CollectionsSheet({ open, onClose }) {
  const enabled = useEnabledModules();
  const navigate = useNavigate();
  if (!open) return null;
  return (
    <div className="modal-scrim sheet-scrim" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <h2>Collections</h2>
        {enabled.map((m) => (
          <button
            key={m.key}
            className="sheet-row"
            onClick={() => {
              navigate(PATHS[m.key]);
              onClose();
            }}
          >
            <Icon id={m.icon} />
            <span className="sheet-text">
              <strong>{m.label}</strong>
              <small>{m.blurb}</small>
            </span>
          </button>
        ))}
        <button
          className="sheet-row muted"
          onClick={() => {
            navigate("/settings");
            onClose();
          }}
        >
          <Icon id="sliders" />
          <span className="sheet-text">
            <strong>Settings</strong>
            <small>Name, collections, display</small>
          </span>
        </button>
      </div>
    </div>
  );
}

function Shell() {
  const { settings } = useSettings();
  const [sheet, setSheet] = useState(false);
  const name = settings?.owner_name;

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand-link">
          <h1 className="brand">
            <Icon id="coin" />
            {name ? `${name}’s` : "Your"} <em>Loot</em>
          </h1>
        </Link>
        <Link to="/settings" className="ghost icon" title="Settings">
          <Icon id="sliders" />
        </Link>
      </header>

      <main className="content">
        <Routes>
          <Route path="/" element={<HomePage onOpenCollections={() => setSheet(true)} />} />
          <Route path="/cards" element={<CardsPage />} />
          <Route path="/pokedex" element={<CardsPage initialView="binder" />} />
          <Route path="/wanted" element={<WantedPage />} />
          <Route path="/games" element={<GamesPage />} />
          <Route path="/hardware" element={<HardwarePage />} />
          <Route path="/movies" element={<MoviesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>

      <TabBar onOpenCollections={() => setSheet(true)} />
      <CollectionsSheet open={sheet} onClose={() => setSheet(false)} />
      {settings?.needs_onboarding && <Onboarding />}
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <IconDefs />
      <SettingsProvider>
        <Shell />
      </SettingsProvider>
    </BrowserRouter>
  );
}

export { MODULES, PATHS };
