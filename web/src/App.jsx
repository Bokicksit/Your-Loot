import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Icon, IconDefs } from "./components/Icons.jsx";
import CardsPage from "./pages/CardsPage.jsx";
import PokedexPage from "./pages/PokedexPage.jsx";
import WantedPage from "./pages/WantedPage.jsx";
import GamesPage from "./pages/GamesPage.jsx";
import MoviesPage from "./pages/MoviesPage.jsx";

const TABS = [
  { to: "/cards", icon: "card", label: "Cards" },
  { to: "/pokedex", icon: "ball", label: "Pokédex" },
  { to: "/wanted", icon: "star", label: "Wanted" },
  { to: "/games", icon: "pad", label: "Games" },
  { to: "/movies", icon: "disc", label: "Movies" },
];

export default function App() {
  return (
    <BrowserRouter>
      <IconDefs />
      <header className="topbar">
        <h1 className="brand">
          <Icon id="coin" />
          Get <em>Loot</em>
        </h1>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/cards" replace />} />
          <Route path="/cards" element={<CardsPage />} />
          <Route path="/pokedex" element={<PokedexPage />} />
          <Route path="/wanted" element={<WantedPage />} />
          <Route path="/games" element={<GamesPage />} />
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
    </BrowserRouter>
  );
}
