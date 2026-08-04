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

// A hidden collection's URL (bookmark, old link) shouldn't 404 or silently
// show a page the user turned off — say so and offer the way back.
function RequireModule({ moduleKey, children }) {
  const enabled = useEnabledModules();
  const { settings } = useSettings();
  if (!settings) return null; // still loading
  if (enabled.some((m) => m.key === moduleKey)) return children;
  const label = MODULES.find((m) => m.key === moduleKey)?.label || moduleKey;
  return (
    <div className="empty">
      <span className="glyph"><Icon id="sliders" /></span>
      <strong>{label} is turned off</strong>
      <p>
        Nothing was deleted — your {label.toLowerCase()} are still stored. Turn
        the collection back on to see them.
      </p>
      <Link to="/settings" className="primary">Open settings</Link>
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
          <Route
            path="/cards"
            element={<RequireModule moduleKey="cards"><CardsPage /></RequireModule>}
          />
          <Route
            path="/pokedex"
            element={
              <RequireModule moduleKey="cards">
                <CardsPage initialView="binder" />
              </RequireModule>
            }
          />
          <Route path="/wanted" element={<WantedPage />} />
          <Route
            path="/games"
            element={<RequireModule moduleKey="games"><GamesPage /></RequireModule>}
          />
          <Route
            path="/hardware"
            element={<RequireModule moduleKey="hardware"><HardwarePage /></RequireModule>}
          />
          <Route
            path="/movies"
            element={<RequireModule moduleKey="movies"><MoviesPage /></RequireModule>}
          />
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
