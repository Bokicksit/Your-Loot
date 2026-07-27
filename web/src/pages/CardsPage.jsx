import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import CardTile from "../components/CardTile.jsx";
import { Icon } from "../components/Icons.jsx";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"];
const GRADERS = ["Raw", "PSA", "BGS", "CGC", "TAG", "ACE"];

// Collection view + card-in-hand add flow: search by name + printed number
// (both on the physical card), set optional to narrow.
export default function CardsPage() {
  const [cards, setCards] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", number: "", set: "" });
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [picked, setPicked] = useState(null); // card chosen from results
  const [addVals, setAddVals] = useState({
    own: true,
    condition: "NM",
    grader: "Raw",
    grade: "",
    binder: false, // opt-in: only flagged copies occupy Pokédex binder slots
  });
  const navigate = useNavigate();

  const load = () => {
    api
      .cards(search ? { search } : {})
      .then((d) => {
        setCards(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search]);

  const doSearch = async () => {
    if (searching || form.name.trim().length < 2) return;
    setSearching(true);
    setPicked(null);
    try {
      const params = { name: form.name.trim() };
      if (form.number.trim()) params.number = form.number.trim();
      if (form.set.trim()) params.set = form.set.trim();
      setResults((await api.cardsSearch(params)).items);
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  const confirmAdd = async () => {
    if (!picked) return;
    try {
      if (addVals.own) {
        const graded = addVals.grader !== "Raw";
        await api.addOwned(picked.id, {
          condition: addVals.condition,
          grader: graded ? addVals.grader : null,
          grade: graded && addVals.grade ? addVals.grade : null,
          in_binder: addVals.binder && !!picked.attrs.national_dex_no,
        });
      } else {
        await api.addWanted(picked.id);
      }
      const wantMode = !addVals.own;
      // keep name/set for rapid binder-logging sessions; clear the specifics
      setForm((f) => ({ ...f, number: "" }));
      setResults(null);
      setPicked(null);
      setAddVals({ own: true, condition: "NM", grader: "Raw", grade: "", binder: false });
      if (wantMode) {
        navigate("/wanted");
      } else {
        load();
      }
    } catch (e) {
      alert(e.message);
    }
  };

  const patchCard = (id, status) =>
    setCards((cs) =>
      cs
        .map((c) =>
          c.id === id ? { ...c, owned: status.owned, wanted: status.wanted } : c
        )
        .filter((c) => c.owned.length > 0) // last copy removed -> out of collection
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search my cards…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button
          className={showForm ? "ghost icon" : "primary"}
          onClick={() => setShowForm(!showForm)}
          title={showForm ? "Close" : "Add a card"}
        >
          <Icon id={showForm ? "x" : "plus"} />
          {!showForm && "Add"}
        </button>
      </div>

      {showForm && (
        <div className="add-form">
          <h2>Add a card</h2>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Card name (Mew ex)"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), doSearch())}
            />
            <input
              type="text"
              style={{ maxWidth: "130px" }}
              placeholder="91/108 (opt.)"
              value={form.number}
              onChange={(e) => setForm({ ...form, number: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), doSearch())}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Set (optional — Scarlet & Violet 151)"
              value={form.set}
              onChange={(e) => setForm({ ...form, set: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), doSearch())}
            />
            <button type="button" className="ghost" onClick={doSearch} disabled={searching}>
              {searching ? "…" : "Search"}
            </button>
          </div>

          {results && results.length === 0 && (
            <p className="error">
              <Icon id="alert" />
              No card matches that name + number. Check the set, or reseed the
              card database if it's a brand-new set.
            </p>
          )}
          {results && results.length > 0 && (
            <div className="grid pick-grid">
              {results.map((c) => (
                <div
                  key={c.id}
                  className={`tile pick ${picked?.id === c.id ? "sel" : ""}`}
                  onClick={() => setPicked(picked?.id === c.id ? null : c)}
                >
                  {c.image_url ? (
                    <img src={c.image_url} alt={c.title} loading="lazy" />
                  ) : (
                    <div className="placeholder" data-label={c.title} />
                  )}
                  <div className="tile-info">
                    <strong>{c.title}</strong>
                    <small>
                      {c.attrs.set_name} #{c.attrs.card_number}
                      {c.attrs.set_total ? `/${c.attrs.set_total}` : ""}
                    </small>
                    <small>{c.attrs.rarity}</small>
                  </div>
                </div>
              ))}
            </div>
          )}

          {picked && (
            <>
              <div className="form-row">
                <button
                  type="button"
                  className={`toggle ${addVals.own ? "on" : ""}`}
                  onClick={() => setAddVals({ ...addVals, own: !addVals.own })}
                >
                  {addVals.own ? "I own it" : "I want it"}
                </button>
                {addVals.own && picked.attrs.national_dex_no && (
                  <button
                    type="button"
                    className={`toggle ${addVals.binder ? "on" : ""}`}
                    onClick={() => setAddVals({ ...addVals, binder: !addVals.binder })}
                    title="This copy goes in the Pokédex binder"
                  >
                    Binder
                  </button>
                )}
                <select
                  disabled={!addVals.own}
                  value={addVals.condition}
                  onChange={(e) => setAddVals({ ...addVals, condition: e.target.value })}
                >
                  {CONDITIONS.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
                <select
                  disabled={!addVals.own}
                  value={addVals.grader}
                  onChange={(e) => setAddVals({ ...addVals, grader: e.target.value })}
                >
                  {GRADERS.map((g) => (
                    <option key={g}>{g}</option>
                  ))}
                </select>
                <input
                  type="text"
                  inputMode="decimal"
                  style={{ maxWidth: "70px" }}
                  placeholder="9.5"
                  disabled={!addVals.own || addVals.grader === "Raw"}
                  value={addVals.grade}
                  onChange={(e) => setAddVals({ ...addVals, grade: e.target.value })}
                />
                <button className="primary" onClick={confirmAdd}>
                  <Icon id="plus" />
                  Add
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {error && (
        <p className="error">
          <Icon id="alert" />
          {error}
        </p>
      )}
      {!error && loaded && cards.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="card" /></span>
          <strong>{search ? `No cards match “${search}”` : "No cards yet"}</strong>
          <p>
            {search
              ? "Try another name — this searches your collection."
              : "Hit Add and punch in the name + number printed on the card."}
          </p>
          {search && (
            <button className="ghost" onClick={() => setSearch("")}>
              Clear search
            </button>
          )}
        </div>
      )}

      <div className="grid">
        {cards.map((c) => (
          <CardTile key={c.id} card={c} onChange={patchCard} />
        ))}
      </div>
    </div>
  );
}
