import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import CardTile from "../components/CardTile.jsx";
import { Icon } from "../components/Icons.jsx";
import RarityMark from "../components/RarityMark.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import PokedexView from "./PokedexPage.jsx";
import { useSettings } from "../settings.jsx";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"];
const GRADERS = ["Raw", "PSA", "BGS", "CGC", "TAG", "ACE"];
const VARIANTS = ["Non-Holo", "Reverse Holo", "Holo"];

// Collection view + card-in-hand add flow: search by name + printed number
// (both on the physical card), set optional to narrow.
export default function CardsPage({ initialView = "collection" }) {
  const { settings, save } = useSettings();
  const [view, setView] = useState(initialView); // collection | binder
  const [cards, setCards] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [facets, setFacets] = useState({ sets: [], rarities: [] });
  const [setFilter, setSetFilter] = useState("");
  const [rarityFilter, setRarityFilter] = useState("");
  const showBinder = !!settings?.show_binder_in_collection; // from Settings
  const [sets, setSets] = useState([]); // for the set autocomplete
  const [manual, setManual] = useState(null); // manual catalog entry draft
  const [online, setOnline] = useState(null); // TCGdex results (null = not searched)
  const [onlineBusy, setOnlineBusy] = useState(false);
  const [setHints, setSetHints] = useState([]); // autocomplete, 2+ chars
  const [setBrowser, setSetBrowser] = useState(null); // browse-all filter text

  // suggest sets only once there's something to go on — 176 sets in a
  // dropdown is noise, not help
  const suggestSets = (text) => {
    const t = text.trim().toLowerCase();
    if (t.length < 2) return setSetHints([]);
    const hit = (s) =>
      (s.abbr || "").toLowerCase().startsWith(t) ||
      (s.code || "").toLowerCase().startsWith(t) ||
      (s.name || "").toLowerCase().includes(t);
    setSetHints(sets.filter(hit).slice(0, 8));
  };

  const chooseSet = (s) => {
    setForm((f) => ({ ...f, set: s.abbr || s.name }));
    setSetHints([]);
    setSetBrowser(null);
  };
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
    keeper: false, // binder card is "the one" vs a placeholder to upgrade
    variant: "Non-Holo",
    stamp: "",
  });
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const load = () => {
    const params = { include_binder: showBinder };
    if (search) params.search = search;
    if (setFilter) params.set_code = setFilter;
    if (rarityFilter) params.rarity = rarityFilter;
    api
      .cards(params)
      .then((d) => {
        setCards(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    api.cardFacets({ include_binder: showBinder }).then((f) => {
      setFacets(f);
      if (setFilter && !f.sets.some((s) => s.code === setFilter)) setSetFilter("");
      if (rarityFilter && !f.rarities.some((r) => r.rarity === rarityFilter))
        setRarityFilter("");
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, setFilter, rarityFilter, showBinder]);

  useEffect(() => {
    api.cardSets().then(setSets).catch(() => {});
  }, []);

  // arriving from the Pokédex ("Find Alakazam cards"): open the add flow
  // pre-filled and run the search straight away
  useEffect(() => {
    const name = searchParams.get("add");
    if (!name) return;
    setShowForm(true);
    setForm((f) => ({ ...f, name, number: "", set: "" }));
    setSearchParams({}, { replace: true });
    (async () => {
      setSearching(true);
      try {
        setResults((await api.cardsSearch({ name })).items);
      } catch (e) {
        alert(e.message);
      } finally {
        setSearching(false);
      }
    })();
  }, [searchParams]);

  const doSearch = async () => {
    if (searching || form.name.trim().length < 2) return;
    setSearching(true);
    setPicked(null);
    try {
      setOnline(null);
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
        const toBinder = addVals.binder && !!picked.attrs.national_dex_no;
        await api.addOwned(picked.id, {
          condition: addVals.condition,
          grader: graded ? addVals.grader : null,
          grade: graded && addVals.grade ? addVals.grade : null,
          in_binder: toBinder,
          variant: addVals.variant === "Non-Holo" ? null : addVals.variant,
          stamp: addVals.stamp.trim() || null,
        });
        if (toBinder) {
          // record whether this occupant is the desired card or a placeholder
          await api.dexHappy(picked.attrs.national_dex_no, addVals.keeper);
        }
      } else {
        await api.addWanted(picked.id);
      }
      const wantMode = !addVals.own;
      // keep name/set for rapid binder-logging sessions; clear the specifics
      setForm((f) => ({ ...f, number: "" }));
      setResults(null);
      setPicked(null);
      setOnline(null);
      setAddVals({
        own: true,
        condition: "NM",
        grader: "Raw",
        grade: "",
        binder: false,
        keeper: false,
        variant: "Non-Holo",
        stamp: "",
      });
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

  const viewSwitch = (
    <div className="chip-row view-switch">
      {[
        ["collection", "Collection"],
        ["binder", "Pokédex"],
      ].map(([k, label]) => (
        <button
          key={k}
          className={`chip ${view === k ? "active" : ""}`}
          onClick={() => setView(k)}
        >
          {label}
        </button>
      ))}
    </div>
  );

  if (view === "binder") {
    return (
      <div>
        {viewSwitch}
        <PokedexView />
      </div>
    );
  }

  return (
    <div>
      {viewSwitch}
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

      <div className="chip-row">
        <button
          type="button"
          className={`toggle ${showBinder ? "on" : ""}`}
          onClick={() => save({ show_binder_in_collection: !showBinder })}
          title="Pokédex cards live in the Pokédex view — toggle to list them here too"
        >
          Pokédex cards
        </button>
        {(facets.sets.length > 0 || facets.rarities.length > 0) && (
          <>
            <select
            className="chip-select"
            title="Filter by set"
            value={setFilter}
            onChange={(e) => setSetFilter(e.target.value)}
          >
            <option value="">All sets</option>
            {facets.sets.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name} ({s.count})
              </option>
            ))}
          </select>
          <select
            className="chip-select"
            title="Filter by rarity"
            value={rarityFilter}
            onChange={(e) => setRarityFilter(e.target.value)}
          >
            <option value="">All rarities</option>
            {facets.rarities.map((r) => (
              <option key={r.rarity} value={r.rarity}>
                {r.rarity} ({r.count})
              </option>
            ))}
            </select>
          </>
        )}
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
              style={{ maxWidth: "150px" }}
              // subset cards print letters ("GG07/GG70"), so say so — the
              // digits-only placeholder read like a digits-only field
              placeholder="91/108 or GG07"
              title="The number printed on the card — letters included (TG03, GG07, RC12)"
              value={form.number}
              onChange={(e) => setForm({ ...form, number: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), doSearch())}
            />
          </div>
          <div className="form-row">
            <span className="set-field">
              <input
                type="text"
                placeholder="Set (optional — 151, MEW, JTG…)"
                value={form.set}
                onChange={(e) => {
                  setForm({ ...form, set: e.target.value });
                  suggestSets(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    setSetHints([]);
                    doSearch();
                  } else if (e.key === "Escape") {
                    setSetHints([]);
                  }
                }}
              />
              {setHints.length > 0 && (
                <ul className="set-hints">
                  {setHints.map((s) => (
                    <li key={s.code || s.name} onClick={() => chooseSet(s)}>
                      <span className="set-abbr">{s.abbr || "—"}</span>
                      <span className="game-text">
                        <strong>{s.name}</strong>
                      </span>
                      <span className="year">{s.year || ""}</span>
                    </li>
                  ))}
                </ul>
              )}
            </span>
            <button
              type="button"
              className="ghost icon"
              title="Browse all sets"
              onClick={() => setSetBrowser(setBrowser === null ? "" : null)}
            >
              <Icon id="sliders" />
            </button>
            <button type="button" className="ghost" onClick={doSearch} disabled={searching}>
              {searching ? "…" : "Search"}
            </button>
          </div>

          {setBrowser !== null && (
            <div className="entry-edit">
              <div className="form-row">
                <input
                  type="text"
                  className="grow"
                  autoFocus
                  placeholder={`Filter ${sets.length} sets…`}
                  value={setBrowser}
                  onChange={(e) => setSetBrowser(e.target.value)}
                />
                <button
                  type="button"
                  className="ghost icon"
                  onClick={() => setSetBrowser(null)}
                  title="Close"
                >
                  <Icon id="x" />
                </button>
              </div>
              <ul className="set-list">
                {sets
                  .filter((s) => {
                    const t = setBrowser.trim().toLowerCase();
                    if (!t) return true;
                    return (
                      (s.name || "").toLowerCase().includes(t) ||
                      (s.abbr || "").toLowerCase().includes(t) ||
                      String(s.year || "").includes(t)
                    );
                  })
                  .map((s) => (
                    <li key={s.code || s.name} onClick={() => chooseSet(s)}>
                      <span className="set-abbr">{s.abbr || "—"}</span>
                      <span className="game-text">
                        <strong>{s.name}</strong>
                      </span>
                      <span className="year">{s.year || ""}</span>
                    </li>
                  ))}
              </ul>
            </div>
          )}

          {/* Shown whenever a search has run, not only on zero hits: a common
              name returns dozens of prints and yours may be none of them, and
              until now that dead end had no way out. */}
          {results && results.length > 0 && (
            <div className="grid pick-grid">
              {results.map((c) => (
                <div
                  key={c.id}
                  className={`tile pick ${picked?.id === c.id ? "sel" : ""}`}
                  onClick={() => {
                    const now = picked?.id === c.id ? null : c;
                    setPicked(now);
                    if (now) {
                      // cards printed as holos default the copy variant
                      setAddVals((v) => ({
                        ...v,
                        variant: /holo/i.test(now.attrs.rarity || "")
                          ? "Holo"
                          : "Non-Holo",
                      }));
                    }
                  }}
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
                    <small>
                      <RarityMark rarity={c.attrs.rarity} /> {c.attrs.rarity}
                    </small>
                  </div>
                </div>
              ))}
            </div>
          )}

          {picked && (
            <>
              {/* swap the art before adding — handy when the catalog has none
                  (new promos) or the wrong print */}
              <div className="form-row wrap">
                <ImagePicker
                  value={picked.image_url}
                  label={picked.image_url ? "Photo" : "Add photo"}
                  onChange={async (url) => {
                    try {
                      const updated = await api.updateCard(picked.id, {
                        image_url: url,
                      });
                      setPicked(updated);
                      setResults((rs) =>
                        rs.map((c) => (c.id === updated.id ? updated : c))
                      );
                    } catch (e) {
                      alert(e.message);
                    }
                  }}
                />
              </div>
              <div className="form-row wrap">
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
                    onClick={() =>
                      setAddVals({
                        ...addVals,
                        binder: !addVals.binder,
                        // IR/SIR pulls default to "the one"; else placeholder
                        keeper: !addVals.binder ? picked.attrs.layer === 3 : false,
                      })
                    }
                    title="This copy goes in the Pokédex"
                  >
                    Pokédex
                  </button>
                )}
                {addVals.own && addVals.binder && picked.attrs.national_dex_no && (
                  <button
                    type="button"
                    className={`toggle ${addVals.keeper ? "on" : ""}`}
                    onClick={() => setAddVals({ ...addVals, keeper: !addVals.keeper })}
                    title="Is this the desired card, or a placeholder to upgrade later?"
                  >
                    {addVals.keeper ? "The one ✓" : "Will upgrade"}
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
                  title="Print style of your copy"
                  value={addVals.variant}
                  onChange={(e) => setAddVals({ ...addVals, variant: e.target.value })}
                >
                  {VARIANTS.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
                <input
                  type="text"
                  style={{ maxWidth: "150px" }}
                  placeholder="Stamp (opt.)"
                  disabled={!addVals.own}
                  value={addVals.stamp}
                  onChange={(e) => setAddVals({ ...addVals, stamp: e.target.value })}
                />
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
          {results && !manual && (
            <div className="form-row wrap">
              {results.length === 0 ? (
                <p className="error" style={{ flex: 1 }}>
                  <Icon id="alert" />
                  Not in the offline card database — try the online catalog,
                  which carries brand-new promo sets.
                </p>
              ) : (
                <p className="game-info-line" style={{ flex: 1 }}>
                  Not the one you're holding? The online catalog carries
                  brand-new promo sets, or enter it yourself.
                </p>
              )}
              <button
                type="button"
                /* the loud action only when there's nothing else to click —
                   with results on screen it shouldn't outrank them */
                className={results.length === 0 ? "primary" : "ghost"}
                disabled={onlineBusy}
                onClick={async () => {
                  setOnlineBusy(true);
                  try {
                    // pass set + number too: a common name has hundreds of
                    // prints online, and these are what pinpoint the card
                    const p = {};
                    if (form.name.trim()) p.name = form.name.trim();
                    if (form.set.trim()) p.set = form.set.trim();
                    if (form.number.trim()) p.number = form.number.trim();
                    setOnline(await api.tcgdexSearch(p));
                  } catch (e) {
                    alert(e.message);
                  } finally {
                    setOnlineBusy(false);
                  }
                }}
              >
                {onlineBusy ? "Searching…" : "Search online catalog"}
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() =>
                  setManual({
                    title: form.name.trim(),
                    set_name: "",
                    set_abbr: form.set.trim().toUpperCase(),
                    card_number: form.number.trim().split("/")[0],
                    set_total: form.number.includes("/")
                      ? form.number.trim().split("/")[1]
                      : "",
                    rarity: "Promo",
                    national_dex_no: "",
                    image_url: null,
                  })
                }
              >
                Add it manually
              </button>
            </div>
          )}

          {online && (
            <>
              <span className="game-info-line">
                Online catalog · {online.length} match{online.length === 1 ? "" : "es"}
              </span>
              {online.length === 0 && (
                <p className="empty" style={{ padding: "var(--s-3)" }}>
                  Nothing online either — add it by hand below.
                </p>
              )}
              <div className="grid pick-grid">
                {online.map((c) => (
                  <div
                    key={c.tcgdex_id}
                    className="tile pick"
                    title="Add this card"
                    onClick={async () => {
                      try {
                        const created = await api.addFromTcgdex(c.tcgdex_id);
                        setResults([created]);
                        setPicked(created);
                        setOnline(null);
                        api.cardSets().then(setSets).catch(() => {});
                      } catch (e) {
                        alert(e.message);
                      }
                    }}
                  >
                    {c.image_url ? (
                      <img src={c.image_url} alt={c.title} loading="lazy" />
                    ) : (
                      <div className="placeholder" data-label="no art yet" />
                    )}
                    <div className="tile-info">
                      <strong>{c.title}</strong>
                      <small>
                        <span className="set-abbr">
                          {(c.set_id || "").toUpperCase()}
                        </span>{" "}
                        #{c.card_number}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {manual && (
            <div className="entry-edit">
              <span className="game-info-line">Manual card entry</span>
              <div className="form-row">
                <input
                  type="text"
                  className="grow"
                  placeholder="Card name"
                  value={manual.title}
                  onChange={(e) => setManual({ ...manual, title: e.target.value })}
                />
                <input
                  type="text"
                  style={{ maxWidth: "110px" }}
                  placeholder="Dex #"
                  inputMode="numeric"
                  value={manual.national_dex_no}
                  onChange={(e) =>
                    setManual({ ...manual, national_dex_no: e.target.value })
                  }
                />
              </div>
              <div className="form-row">
                <input
                  type="text"
                  className="grow"
                  placeholder="Set name (Mega Evolution Promos)"
                  value={manual.set_name}
                  onChange={(e) => setManual({ ...manual, set_name: e.target.value })}
                />
                <input
                  type="text"
                  style={{ maxWidth: "90px" }}
                  placeholder="Code"
                  value={manual.set_abbr}
                  onChange={(e) => setManual({ ...manual, set_abbr: e.target.value })}
                />
              </div>
              <div className="form-row">
                <input
                  type="text"
                  style={{ maxWidth: "90px" }}
                  placeholder="Number"
                  value={manual.card_number}
                  onChange={(e) => setManual({ ...manual, card_number: e.target.value })}
                />
                <input
                  type="text"
                  style={{ maxWidth: "90px" }}
                  placeholder="of total"
                  inputMode="numeric"
                  value={manual.set_total}
                  onChange={(e) => setManual({ ...manual, set_total: e.target.value })}
                />
                <input
                  type="text"
                  className="grow"
                  placeholder="Rarity"
                  value={manual.rarity}
                  onChange={(e) => setManual({ ...manual, rarity: e.target.value })}
                />
              </div>
              <div className="form-row">
                <ImagePicker
                  value={manual.image_url}
                  onChange={(url) => setManual({ ...manual, image_url: url })}
                  label="Photo of the card"
                />
              </div>
              <div className="form-row">
                <button
                  type="button"
                  className="primary"
                  onClick={async () => {
                    if (!manual.title.trim()) return;
                    try {
                      const created = await api.addCard({
                        title: manual.title.trim(),
                        set_name: manual.set_name.trim() || null,
                        set_abbr: manual.set_abbr.trim() || null,
                        card_number: manual.card_number.trim() || null,
                        set_total: manual.set_total ? Number(manual.set_total) : null,
                        rarity: manual.rarity.trim() || null,
                        national_dex_no: manual.national_dex_no
                          ? Number(manual.national_dex_no)
                          : null,
                        image_url: manual.image_url,
                      });
                      // hand off to the normal own/want panel
                      setResults([created]);
                      setPicked(created);
                      setManual(null);
                      api.cardSets().then(setSets).catch(() => {});
                    } catch (err) {
                      alert(err.message);
                    }
                  }}
                >
                  <Icon id="check" />
                  Create card
                </button>
                <button type="button" className="ghost" onClick={() => setManual(null)}>
                  Cancel
                </button>
              </div>
            </div>
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
          <CardTile key={c.id} card={c} onChange={patchCard} onReload={load} />
        ))}
      </div>
    </div>
  );
}
