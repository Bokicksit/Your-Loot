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
import SignIn from "./components/SignIn.jsx";
import { MODULES, SettingsProvider, useEnabledModules, useSettings } from "./settings.jsx";
import HomePage from "./pages/HomePage.jsx";
import CardsPage from "./pages/CardsPage.jsx";
import WantedPage from "./pages/WantedPage.jsx";
import GamesPage from "./pages/GamesPage.jsx";
import HardwarePage from "./pages/HardwarePage.jsx";
import MoviesPage from "./pages/MoviesPage.jsx";
import BooksPage from "./pages/BooksPage.jsx";
import RecordsPage from "./pages/RecordsPage.jsx";
import LegoPage from "./pages/LegoPage.jsx";
import ComicsPage from "./pages/ComicsPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";

const PATHS = {
  cards: "/cards",
  games: "/games",
  hardware: "/hardware",
  movies: "/movies",
  books: "/books",
  records: "/records",
  lego: "/lego",
  comics: "/comics",
};

// Collections opens the full list, Wanted is the hunt, Favourites is the
// shortcut to the ones you starred. Wanted gives up the star to Favourites,
// since a star means "starred" everywhere else in the app.
function TabBar({ onOpenCollections }) {
  const { pathname } = useLocation();
  const inCollection = Object.values(PATHS).some((p) => pathname.startsWith(p));
  return (
    <nav className="tabbar">
      <button
        className={inCollection ? "active" : ""}
        onClick={onOpenCollections}
        aria-haspopup="menu"
      >
        <Icon id="card" />
        <span>Collections</span>
      </button>
      <NavLink to="/wanted">
        <Icon id="target" />
        <span>Wanted</span>
      </NavLink>
      <NavLink to="/" end>
        <Icon id="star" />
        <span>Favourites</span>
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

// Which collection you're looking at wasn't obvious — every page opens on a
// search box and an Add button that look the same everywhere. Named here rather
// than in eight page components, so it stays consistent and a new collection
// gets its heading from the registry for free.
function PageTitle() {
  const { pathname } = useLocation();
  if (pathname.startsWith("/wanted")) {
    return (
      <h2 className="page-title">
        <Icon id="target" />
        Wanted
      </h2>
    );
  }
  // the Pokédex is a view of Cards, not a collection in its own right
  const key = pathname.startsWith("/pokedex")
    ? "cards"
    : Object.keys(PATHS).find((k) => pathname.startsWith(PATHS[k]));
  const module = MODULES.find((m) => m.key === key);
  if (!module) return null; // Favourites and Settings write their own
  return (
    <h2 className="page-title">
      <Icon id={module.icon} />
      {module.label}
    </h2>
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
        <PageTitle />
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
          <Route
            path="/books"
            element={<RequireModule moduleKey="books"><BooksPage /></RequireModule>}
          />
          <Route
            path="/records"
            element={<RequireModule moduleKey="records"><RecordsPage /></RequireModule>}
          />
          <Route
            path="/lego"
            element={<RequireModule moduleKey="lego"><LegoPage /></RequireModule>}
          />
          <Route
            path="/comics"
            element={<RequireModule moduleKey="comics"><ComicsPage /></RequireModule>}
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
      {/* Outside SettingsProvider on purpose: settings are per-person now, so
          asking for them before knowing who is asking gets a 401 and a
          pointless reload. A single-user install passes straight through. */}
      <SignIn>
        <SettingsProvider>
          <Shell />
        </SettingsProvider>
      </SignIn>
    </BrowserRouter>
  );
}

export { MODULES, PATHS };
