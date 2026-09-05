import { useEffect, useState } from "react";
import ImagePicker from "../components/ImagePicker.jsx";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { BinderSwitch } from "../components/BinderGrid.jsx";
import BinderShape from "../components/BinderShape.jsx";
import ViewToggle, { useTileView } from "../components/ViewToggle.jsx";
import { useHasJapanese, usePublicProfiles } from "../settings.jsx";
import { refreshBinders } from "../mybinders.js";

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
  const [arranging, setArranging] = useState(false);
  // which binder's settings are open, if any — the shelf stays where it is
  const [editing, setEditing] = useState(null);
  const [lifted, setLifted] = useState(null); // the binder in your hand
  const [tiles] = useTileView("binders");

  const load = () => api.binders().then((d) => setShelf(d.binders)).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const made = () => {
    setAdding(null);
    load();
  };

  /** The same two taps that arrange a binder, arranging the shelf.
   *
   *  Kind and then name is a reasonable order and nobody's actual one — a
   *  real shelf is arranged by what you reach for, the set you are working
   *  through at eye level and the trades pile at the end.
   */
  const place = async (targetId) => {
    const ids = shelf.map((b) => b.id);
    const from = ids.indexOf(lifted);
    const to = ids.indexOf(targetId);
    setLifted(null);
    if (from < 0 || to < 0 || from === to) return;
    const [moved] = ids.splice(from, 1);
    ids.splice(to, 0, moved);
    setShelf(ids.map((i) => shelf.find((b) => b.id === i)));  // land the tap first
    await api.reorderShelf(ids);
    load();
  };

  const tap = (e, binder) => {
    if (!arranging) return;                 // otherwise the Link does its job
    e.preventDefault();
    if (lifted === null) setLifted(binder.id);
    else if (lifted === binder.id) setLifted(null);
    else place(binder.id);
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

      {/* Its own row, as everywhere else in this app: the two above make a
          binder, these two decide how the shelf is drawn. Together they wanted
          505px of a phone's 343 and the auto-margin put the toggle on top of a
          button. */}
      <div className="chip-row">
        <ViewToggle module="binders" />
        {shelf?.length > 1 && (
          <button
            className={`chip ${arranging ? "active" : ""}`}
            onClick={() => {
              setArranging(!arranging);
              setLifted(null);
              setAdding(null);
            }}
          >
            <Icon id="sliders" />
            {arranging ? "Done" : "Arrange"}
          </button>
        )}
      </div>

      {arranging && (
        <p className="settings-note arrange-hint">
          {lifted === null
            ? "Tap a binder to pick it up."
            : "Now tap where it should go — or tap it again to put it back."}
        </p>
      )}

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

      {editing && (
        <BinderSettings
          binder={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}

      <div className={`binder-shelf ${tiles ? "as-tiles" : ""}`}>
        {(shelf || []).map((b) => (
          <div className="binder-slot" key={b.id}>
          <Link
            // straight to the Pokédex rather than through a binder page that
            // only redirects there
            to={b.kind === "dex" ? "/pokedex" : `/binders/${b.id}`}
            className={`binder-card ${lifted === b.id ? "lifted" : ""} ${arranging ? "arranging" : ""}`}
            onClick={(e) => tap(e, b)}
          >
            {b.image_url ? (
              // Not lazy. A shelf holds a handful of covers and they are all
              // near the top, so deferring them saves nothing — and the width
              // is computed from the image's own proportions, which the
              // browser cannot know until it has actually loaded one.
              <img className="binder-cover" src={b.image_url} data-item={b.id} alt="" />
            ) : b.color ? (
              // A colour you chose beats one the app made up, and beats
              // photographing a plain folder to prove it is plain.
              <span
                className="binder-cover flat"
                style={{ "--c": b.color }}
                aria-hidden="true"
              />
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
                ? pocketWords(b)
                : `${b.filled} / ${b.total}`}
              {b.kind !== "custom" && b.missing > 0 && <em> · {b.missing} missing</em>}
            </span>
            {b.kind !== "custom" && (
              <span className="binder-bar" aria-hidden="true">
                <span style={{ width: `${b.total ? (b.filled / b.total) * 100 : 0}%` }} />
              </span>
            )}
          </Link>
          {/* Not while the shelf is being rearranged: a tap then means
              "put it here", and a second thing to hit would be a trap. */}
          {!arranging && (
            <button
              type="button"
              className="binder-edit"
              title={`Settings for ${b.name}`}
              aria-label={`Settings for ${b.name}`}
              onClick={() => setEditing(b)}
            >
              <Icon id="pencil" />
            </button>
          )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** A binder's settings, from the shelf.
 *
 *  The same control the binder's own page uses, in front of the shelf rather
 *  than inside the binder — changing how a binder is set up is not a reason
 *  to have to open it, and on a shelf of eight it is the difference between
 *  one press and three.
 *
 *  Deliberately not everything: the cover picker belongs where the cards are,
 *  and a shelf is not where somebody sets about photographing a folder.
 */
function BinderSettings({ binder, onClose, onSaved }) {
  const hasJapanese = useHasJapanese();
  const profiles = usePublicProfiles();
  const [name, setName] = useState(binder.name);
  const [shape, setShape] = useState({
    rows: binder.rows ?? 3,
    cols: binder.cols ?? 3,
    double_page: !!binder.double_page,
    allow_ja: !!binder.allow_ja,
    on_profile: binder.on_profile !== false,
    color: binder.color || null,
    pages: binder.pages ?? 0,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const save = async (ev) => {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // Only what changed. A binder's shape is safe to send whole, but its
      // page count is not — "pages" on an untouched binder would resize it
      // to whatever the shelf happened to report.
      const patch = {};
      if (name.trim() && name.trim() !== binder.name) patch.name = name.trim();
      if (shape.rows !== (binder.rows ?? 3)) patch.rows = shape.rows;
      if (shape.cols !== (binder.cols ?? 3)) patch.cols = shape.cols;
      if (shape.double_page !== !!binder.double_page) {
        patch.double_page = shape.double_page;
      }
      if (shape.allow_ja !== !!binder.allow_ja) patch.allow_ja = shape.allow_ja;
      if (shape.on_profile !== (binder.on_profile !== false)) {
        patch.on_profile = shape.on_profile;
      }
      if ((shape.color || null) !== (binder.color || null)) {
        patch.color = shape.color || "";
      }
      if (binder.kind === "custom" && shape.pages !== (binder.pages ?? 0)) {
        patch.pages = shape.pages;
      }
      if (Object.keys(patch).length) await api.editBinder(binder.id, patch);
      refreshBinders();
      onSaved();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="filter-sheet binder-sheet" onSubmit={save}>
      <label className="set-field">
        <span className="set-label">Name</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={60}
          required
        />
      </label>
      <BinderShape
        value={shape}
        onChange={setShape}
        showPages={binder.kind === "custom"}
        showJapanese={binder.kind !== "set" && hasJapanese}
        showProfile={profiles}
        pageHint={
          "Grows the binder with empty pages, or takes empty ones off the " +
          "end. It will not drop a page that still has a card in it."
        }
      />
      {error && <p className="error">{error}</p>}
      <div className="sheet-actions">
        <button type="submit" className="primary" disabled={busy}>
          <Icon id="check" />
          {busy ? "…" : "Save"}
        </button>
        <button type="button" className="ghost" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  );
}

/** Pick a set. Ordered newest first, and each row says how many of it you
 *  already own — which is the number that decides whether a binder of it is
 *  worth keeping. */
/** What a binder of your own holds, said the way a person would.
 *
 *  "9 cards" on a binder with nothing in it was the pocket count wearing the
 *  wrong word. Empty pockets are empty pockets; cards are cards; a binder
 *  with both says both. */
function pocketWords(b) {
  const empty = Math.max(0, (b.total || 0) - (b.filled || 0));
  const cards = b.filled || 0;
  if (!b.total) return "empty";
  if (!cards) return `${empty} empty ${empty === 1 ? "pocket" : "pockets"}`;
  if (!empty) return `${cards} ${cards === 1 ? "card" : "cards"}`;
  return `${cards} ${cards === 1 ? "card" : "cards"} · ${empty} empty`;
}

function AddSetBinder({ onDone, onCancel }) {
  const [sets, setSets] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [master, setMaster] = useState(false);
  const [cover, setCover] = useState(null);
  const [error, setError] = useState(null);
  // No page count here: a set binder's pages are however many it takes to
  // hold the set, which the set already decides.
  const [shape, setShape] = useState({
    rows: 3, cols: 3, double_page: false, color: null,
  });

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
        ...shape,
        image_url: cover || undefined,
      });
      refreshBinders();
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="filter-sheet binder-sheet">
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
      <BinderShape value={shape} onChange={setShape} />
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
      {/* Optional, and chosen first: the binder is made the moment you tap a
          set, so anything you want on it has to be ready by then. */}
      <ImagePicker label="Cover (optional)" value={cover} onChange={setCover} />
      <button type="button" className="ghost" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}

function AddCustomBinder({ onDone, onCancel }) {
  const [name, setName] = useState("");
  const [cover, setCover] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [shape, setShape] = useState({
    rows: 3, cols: 3, double_page: false, color: null, pages: 0,
  });

  const make = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createBinder({
        name: name.trim(), kind: "custom", ...shape, image_url: cover || undefined,
      });
      refreshBinders();
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="filter-sheet binder-sheet" onSubmit={make}>
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
      <BinderShape value={shape} onChange={setShape} showPages />
      {error && <p className="error">{error}</p>}
      <ImagePicker label="Cover (optional)" value={cover} onChange={setCover} />
      <div className="sheet-actions">
        <button type="submit" className="primary" disabled={busy || !name.trim()}>
          <Icon id="check" />
          {busy ? "…" : "Make it"}
        </button>
        <button type="button" className="ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
