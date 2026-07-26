import { useEffect, useState } from "react";
import { api } from "../api.js";
import CardTile from "../components/CardTile.jsx";
import { Icon } from "../components/Icons.jsx";

export default function CardsPage() {
  const [cards, setCards] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .cards(search ? { search } : {})
        .then((data) => {
          setCards(data.items);
          setTotal(data.total);
          setError(null);
          setLoaded(true);
        })
        .catch((e) => setError(e.message));
    }, 250); // debounce typing
    return () => clearTimeout(t);
  }, [search]);

  const patchCard = (id, status) =>
    setCards((cs) =>
      cs.map((c) =>
        c.id === id ? { ...c, owned: status.owned, wanted: status.wanted } : c
      )
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search cards…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
      </div>
      {error && (
        <p className="error">
          <Icon id="alert" />
          {error}
        </p>
      )}
      <div className="grid">
        {cards.map((c) => (
          <CardTile key={c.id} card={c} onChange={patchCard} />
        ))}
      </div>
      {!error && loaded && cards.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="card" /></span>
          <strong>{search ? `No cards match “${search}”` : "No cards yet"}</strong>
          <p>
            {search
              ? "Try a set name, a dex number, or clear the search."
              : "Run the seed script to load your card database — see the README."}
          </p>
          {search && (
            <button className="ghost" onClick={() => setSearch("")}>
              Clear search
            </button>
          )}
        </div>
      )}
    </div>
  );
}
