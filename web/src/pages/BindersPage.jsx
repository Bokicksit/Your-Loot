import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { BinderSwitch } from "../components/BinderGrid.jsx";

/** A binder with no cover still needs a front.
 *
 *  The hue comes from the kind first — a set binder is jade, a master set
 *  blue, one of your own violet, the Pokédex gold — so the colour repeats
 *  what the label says instead of being decoration. A little of the name is
 *  mixed in on top, so two set binders are not identical twins on the shelf.
 */
const KIND_HUE = { dex: 75, set: 165, master: 255, custom: 305 };

function fillerHue(binder) {
  const base = KIND_HUE[binder.kind === "set" && binder.master ? "master" : binder.kind] ?? 300;
  let n = 0;
  for (const ch of binder.name || "") n = (n * 31 + ch.charCodeAt(0)) % 1000;
  return base + (n % 34) - 17;
}


/** The shelf: every binder you keep, and the way to start another.
 *
 *  Two kinds can be made here. A **set** binder is a whole set with a slot
 *  per card, filled by what you already own — nothing to file, so it is
 *  useful the moment it exists and mostly answers "what am I missing". A
 *  **custom** binder starts empty and holds whatever you put in it, in the
 *  order you put it: the binder of nothing but Charizards.
 *
 *  The Pokédex is on this shelf too but is not made or unmade here — there is
 *  one, it has always been there, and the only interesting thing about it is
 *  how full it is.
 */
export default function BindersPage() {
  const [shelf, setShelf] = useState(null);
  const [adding, setAdding] = useState(null); // null | "set" | "custom"
  const [error, setError] = useState(null);

  const load = () => api.binders().then((d) => setShelf(d.binders)).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const made = () => {
    setAdding(null);
    load();
  };

  return (
    <div>
      <BinderSwitch active="binders" />

      <div className="chip-row">
        <button className="chip" onClick={() => setAdding("set")}>
          <Icon id="plus" />
          Binder of a set
        </button>
        <button className="chip" onClick={() => setAdding("custom")}>
          <Icon id="plus" />
          Binder of your own
        </button>
      </div>

      {adding === "set" && <AddSetBinder onDone={made} onCancel={() => setAdding(null)} />}
      {adding === "custom" && <AddCustomBinder onDone={made} onCancel={() => setAdding(null)} />}

      {error && (
        <p className="error">
          <Icon id="alert" />
          {error}
        </p>
      )}

      {shelf === null && <p className="empty">Loading…</p>}
      {shelf?.length === 0 && (
        <p className="empty">
          No binders yet. A set binder shows a whole set with the gaps in it; a
          binder of your own holds whatever you choose.
        </p>
      )}

      <div className="binder-shelf">
        {(shelf || []).map((b) => (
          <Link key={b.id} to={`/binders/${b.id}`} className="binder-card">
            {b.image_url ? (
              // Not lazy. A shelf holds a handful of covers and they are all
              // near the top, so deferring them saves nothing — and the width
              // is computed from the image's own proportions, which the
              // browser cannot know until it has actually loaded one.
              <img className="binder-cover" src={b.image_url} alt="" />
            ) : (
              <span
                className="binder-cover filler"
                style={{ "--h": fillerHue(b) }}
                aria-hidden="true"
              />
            )}
            <span className="binder-kind">
              <Icon id={b.kind === "dex" ? "ball" : b.kind === "set" ? "card" : "star"} />
              {b.kind === "dex"
                ? "Pokédex"
                : b.kind === "set"
                ? b.master ? "Master set" : "Set"
                : "Custom"}
            </span>
            <strong>{b.name}</strong>
            <span className="binder-count">
              {/* A custom binder has no target size, so "3 of 3" would be
                  answering a question nobody asked. The other two are a set
                  universe you are working through. */}
              {b.kind === "custom"
                ? `${b.total} ${b.total === 1 ? "card" : "cards"}`
                : `${b.filled} / ${b.total}`}
              {b.kind !== "custom" && b.missing > 0 && <em> · {b.missing} missing</em>}
            </span>
            {b.kind !== "custom" && (
              <span className="binder-bar" aria-hidden="true">
                <span style={{ width: `${b.total ? (b.filled / b.total) * 100 : 0}%` }} />
              </span>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}

/** Pick a set. Ordered newest first, and each row says how many of it you
 *  already own — which is the number that decides whether a binder of it is
 *  worth keeping. */
function AddSetBinder({ onDone, onCancel }) {
  const [sets, setSets] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [master, setMaster] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.binderSets().then((d) => setSets(d.sets)).catch((e) => setError(e.message));
  }, []);

  const shown = (sets || [])
    .filter((s) => {
      const t = q.trim().toLowerCase();
      if (!t) return true;
      return [s.name, s.abbr, s.code].some((x) => (x || "").toLowerCase().includes(t));
    })
    .slice(0, 60);

  const make = async (s) => {
    setBusy(true);
    setError(null);
    try {
      await api.createBinder({
        name: master ? `${s.name} — master` : s.name,
        kind: "set",
        set_code: s.code,
        master,
      });
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="filter-sheet">
      <label>
        <span>Which set</span>
        <input
          type="search"
          className="grow"
          autoFocus
          placeholder="Prismatic Evolutions, Celebrations, 151…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </label>
      <div className="form-row">
        <span className="settings-label">Master set</span>
        <button
          type="button"
          className={`toggle ${master ? "on" : ""}`}
          onClick={() => setMaster(!master)}
        >
          {master ? "Every printing" : "One per card"}
        </button>
      </div>
      <p className="settings-note">
        {master
          ? "A slot for each way a card was printed — plain, reverse holo, holo — so a set is only complete when you have them all. The printings are looked up when the binder is made, which takes a moment."
          : "One slot per card in the set, whichever way it was printed."}
      </p>
      {error && <p className="error">{error}</p>}
      {sets === null ? (
        <p className="empty">Loading sets…</p>
      ) : (
        <div className="set-picker">
          {shown.map((s) => (
            <button
              key={s.code}
              type="button"
              className="set-row"
              disabled={busy || (master ? s.has_master : s.has_binder)}
              onClick={() => make(s)}
              title={(master ? s.has_master : s.has_binder) ? "You already have this binder" : ""}
            >
              <span className="set-name">
                {s.name}
                {s.abbr && <em> {s.abbr}</em>}
              </span>
              <span className="set-meta">
                {s.year || ""} · {s.cards} cards
                {s.owned > 0 && <strong> · you own {s.owned}</strong>}
                {(master ? s.has_master : s.has_binder) && <em> · already made</em>}
              </span>
            </button>
          ))}
          {shown.length === 0 && <p className="empty">No set matches that.</p>}
        </div>
      )}
      <button type="button" className="ghost" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}

function AddCustomBinder({ onDone, onCancel }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const make = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createBinder({ name: name.trim(), kind: "custom" });
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="filter-sheet" onSubmit={make}>
      <label>
        <span>Call it</span>
        <input
          type="text"
          className="grow"
          autoFocus
          maxLength={60}
          placeholder="Charizards, Trades, Favourites…"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" className="primary" disabled={busy || !name.trim()}>
        <Icon id="check" />
        {busy ? "…" : "Make it"}
      </button>
      <button type="button" className="ghost" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}
