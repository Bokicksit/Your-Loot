import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import BarcodeScan from "../components/BarcodeScan.jsx";
import { Icon } from "../components/Icons.jsx";
import { cleanGameTitle } from "../upc.js";

const REGIONS = ["NTSC-U", "PAL", "NTSC-J", "Region-free"];
const CONDITIONS = ["Mint", "Good", "Fair", "Poor"];
const COMPLETENESS = ["loose", "CIB", "sealed"];

// NTSC-U default until there's a settings screen for it
const EMPTY_FORM = {
  title: "",
  platform_id: "",
  region: "NTSC-U",
  is_hardware: false,
  igdb_id: null,
  image_url: null,
  own: true, // most additions are things already on the shelf
  completeness: "CIB",
  condition: "Good",
};

// best-effort map from IGDB platform names to our lookup table.
// Order matters: exact, then prefix ("Super Nintendo" prefixes "Super Nintendo
// Entertainment System"), then substring — plain substring alone would map
// SNES to NES, since "…Nintendo Entertainment System" contains the NES name.
function matchPlatform(igdbNames, platforms) {
  for (const name of igdbNames) {
    const n = name.toLowerCase();
    const exact = platforms.find((p) => p.name.toLowerCase() === n);
    if (exact) return exact.id;
    const prefix = platforms
      .filter((p) => n.startsWith(p.name.toLowerCase()))
      .sort((a, b) => b.name.length - a.name.length)[0];
    if (prefix) return prefix.id;
    const partial = platforms
      .filter((p) => n.includes(p.name.toLowerCase()) || p.name.toLowerCase().includes(n))
      .sort((a, b) => b.name.length - a.name.length)[0];
    if (partial) return partial.id;
  }
  return "";
}

export default function GamesPage() {
  const [games, setGames] = useState([]);
  const [total, setTotal] = useState(0);
  const [platforms, setPlatforms] = useState([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all"); // all | games | hardware
  const [platformFilter, setPlatformFilter] = useState(""); // system; genre later
  const [usedPlatforms, setUsedPlatforms] = useState([]); // only what's in the collection
  const [sort, setSort] = useState("title"); // title | platform | added
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [results, setResults] = useState(null); // null = no search yet
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.platforms().then(setPlatforms);
  }, []);

  const load = () => {
    const params = { sort };
    if (search) params.search = search;
    if (filter !== "all") params.is_hardware = filter === "hardware";
    if (platformFilter) params.platform_id = platformFilter;
    api
      .games(params)
      .then((d) => {
        setGames(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    // keep the system filter honest: only platforms with entries, with counts
    api.platformsInUse().then((used) => {
      setUsedPlatforms(used);
      if (platformFilter && !used.some((p) => String(p.id) === String(platformFilter))) {
        setPlatformFilter(""); // selected system's last entry was deleted
      }
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, filter, platformFilter, sort]);

  const igdbSearch = async () => {
    if (form.title.trim().length < 2 || searching) return;
    setSearching(true);
    try {
      setResults(await api.igdbSearch(form.title.trim()));
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  // barcode (CIB boxes) → product title → auto-run the IGDB search
  const onBarcode = async (code) => {
    try {
      const res = await api.barcodeLookup(code);
      if (!res.found) {
        alert("No product match for that barcode — type the title instead.");
        return;
      }
      const raw = res.titles[0].title;
      const title = cleanGameTitle(raw) || raw;
      setForm((f) => ({ ...f, title, igdb_id: null, image_url: null }));
      setSearching(true);
      try {
        setResults(await api.igdbSearch(title));
      } finally {
        setSearching(false);
      }
    } catch (e) {
      alert(e.message);
    }
  };

  const pickResult = (r) => {
    setForm({
      ...form,
      title: r.year ? `${r.title} (${r.year})` : r.title,
      igdb_id: r.igdb_id,
      image_url: r.cover_url, // IGDB cover = box art
      platform_id: matchPlatform(r.platforms, platforms) || form.platform_id,
    });
    setResults(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      const created = await api.addGame({
        title: form.title,
        platform_id: form.platform_id ? Number(form.platform_id) : null,
        region: form.region || null,
        is_hardware: form.is_hardware,
        igdb_id: form.igdb_id,
        image_url: form.image_url,
      });
      if (form.own) {
        // catalog + first copy in one go
        await api.addOwned(created.id, {
          condition: form.condition,
          completeness: form.completeness,
        });
      } else {
        // "I want it": straight to the wanted list — it won't appear in the
        // library until a copy is owned, so jump there for visible feedback
        await api.addWanted(created.id);
      }
      const wantMode = !form.own;
      setForm(EMPTY_FORM);
      setResults(null);
      setShowForm(false);
      if (wantMode) {
        navigate("/wanted");
      } else {
        load();
      }
    } catch (err) {
      alert(err.message);
    }
  };

  const patchGame = (id, status) =>
    setGames((gs) =>
      gs.map((g) =>
        g.id === id ? { ...g, owned: status.owned, wanted: status.wanted } : g
      )
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search games…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button
          className={showForm ? "ghost icon" : "primary"}
          onClick={() => setShowForm(!showForm)}
          title={showForm ? "Close" : "Add to library"}
        >
          <Icon id={showForm ? "x" : "plus"} />
          {!showForm && "Add"}
        </button>
      </div>

      <div className="chip-row">
        {["all", "games", "hardware"].map((f) => (
          <button
            key={f}
            className={`chip ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "games" && <Icon id="pad" />}
            {f === "hardware" && <Icon id="sliders" />}
            {f[0].toUpperCase() + f.slice(1)}
          </button>
        ))}
        <select
          className="chip-select"
          title="Filter by system"
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
        >
          <option value="">All systems</option>
          {usedPlatforms.map((p) => (
            <option key={p.id} value={p.id}>
              {p.abbreviation || p.name} ({p.count})
            </option>
          ))}
        </select>
        <select
          className="chip-select"
          title="Sort"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="title">A–Z</option>
          <option value="platform">By system</option>
          <option value="added">Last added</option>
        </select>
      </div>

      {showForm && (
        <form className="add-form" onSubmit={submit}>
          <h2>Add to library</h2>
          <div className="form-row">
            <input
              type="text"
              required
              placeholder="Title — then search IGDB"
              value={form.title}
              onChange={(e) =>
                // manual edits detach the IGDB link/cover
                setForm({ ...form, title: e.target.value, igdb_id: null, image_url: null })
              }
              onKeyDown={(e) => {
                // Enter always searches IGDB — the form only submits via Add
                if (e.key === "Enter") {
                  e.preventDefault();
                  igdbSearch();
                }
              }}
            />
            <button type="button" className="ghost" onClick={igdbSearch} disabled={searching}>
              {searching ? "…" : "Search IGDB"}
            </button>
            <BarcodeScan onCode={onBarcode} />
          </div>
          <div className="form-row">
            <select
              value={form.platform_id}
              onChange={(e) => setForm({ ...form, platform_id: e.target.value })}
            >
              <option value="">Platform…</option>
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <select
              value={form.region}
              onChange={(e) => setForm({ ...form, region: e.target.value })}
            >
              <option value="">Region…</option>
              {REGIONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <button
              type="button"
              className={`toggle ${form.own ? "on" : ""}`}
              onClick={() => setForm({ ...form, own: !form.own })}
            >
              {form.own ? "I own it" : "I want it"}
            </button>
            <select
              title="Completeness"
              disabled={!form.own}
              value={form.completeness}
              onChange={(e) => setForm({ ...form, completeness: e.target.value })}
            >
              {COMPLETENESS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <select
              title="Condition"
              disabled={!form.own}
              value={form.condition}
              onChange={(e) => setForm({ ...form, condition: e.target.value })}
            >
              {CONDITIONS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            {form.igdb_id && (
              <span className="igdb-linked">
                <Icon id="link" />
                IGDB #{form.igdb_id} linked
              </span>
            )}
            <button
              type="button"
              className={`toggle ${form.is_hardware ? "on" : ""}`}
              onClick={() => setForm({ ...form, is_hardware: !form.is_hardware })}
            >
              Hardware
            </button>
            <button type="submit" className="primary" style={{ marginLeft: "auto" }}>
              <Icon id="plus" />
              Add
            </button>
          </div>
          {results && (
            <ul className="igdb-results">
              {results.length === 0 && (
                <li style={{ cursor: "default", color: "var(--text-mute)" }}>
                  No IGDB matches.
                </li>
              )}
              {results.map((r) => (
                <li key={r.igdb_id} onClick={() => pickResult(r)}>
                  {r.cover_url ? (
                    <img src={r.cover_url} alt="" loading="lazy" />
                  ) : (
                    <span className="placeholder" data-label="" />
                  )}
                  <span className="game-text">
                    <strong>{r.title}</strong>
                    <small>{r.platforms.slice(0, 4).join(", ")}</small>
                  </span>
                  <span className="year">{r.year || ""}</span>
                </li>
              ))}
            </ul>
          )}
        </form>
      )}

      {error && (
        <p className="error">
          <Icon id="alert" />
          {error}
        </p>
      )}
      {!error && loaded && games.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="pad" /></span>
          <strong>No games yet</strong>
          <p>Hit Add and search IGDB, or enter consoles and carts by hand.</p>
        </div>
      )}

      <div className="game-list">
        {games.map((g) => (
          <GameRow key={g.id} game={g} onChange={patchGame} onDelete={load} />
        ))}
      </div>
    </div>
  );
}

// Shows /platforms/<ABBR>.svg when that file exists in web/public/platforms/
// (drop in any logo pack you like); falls back to a styled abbreviation tag.
function PlatformBadge({ abbr, name }) {
  const [hasLogo, setHasLogo] = useState(true);
  const label = abbr || name;
  if (!label) return null;
  return hasLogo ? (
    <img
      className="plat-logo"
      src={`/platforms/${label}.svg`}
      alt={label}
      title={name || label}
      onError={() => setHasLogo(false)}
    />
  ) : (
    <span className="plat-badge" title={name || label}>{label}</span>
  );
}

function GameRow({ game, onChange, onDelete }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // owned id being edited
  const [editVals, setEditVals] = useState({ completeness: "CIB", condition: "Good" });

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      const status = await fn();
      onChange(game.id, status);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeCopy = (ownedId) => run(() => api.removeOwned(game.id, ownedId));

  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      completeness: o.completeness || "CIB",
      condition: o.condition || "Good",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const status = await api.updateOwned(game.id, editing, editVals);
      setEditing(null);
      return status;
    });
  // no want-star here: wanting happens at add time ("I want it") and is
  // managed on the Wanted tab — library rows are for owned copies
  const del = async () => {
    if (!confirm(`Delete "${game.title}" and its records?`)) return;
    await api.deleteGame(game.id);
    onDelete();
  };

  return (
    <div className={`game-row ${game.owned.length ? "row-owned" : ""}`}>
      {game.image_url ? (
        <img className="game-cover" src={game.image_url} alt="" loading="lazy" />
      ) : (
        <span className="game-icon">
          <Icon id={game.attrs.is_hardware ? "pad" : "disc"} />
        </span>
      )}
      <span className="game-text">
        <strong>{game.title}</strong>
        <small className="game-meta">
          <PlatformBadge abbr={game.attrs.platform_abbr} name={game.attrs.platform_name} />
          {game.attrs.region && <span>{game.attrs.region}</span>}
        </small>
        {game.owned.length > 0 && (
          <span className="copy-chips">
            {game.owned.map((o) => (
              <span
                key={o.id}
                className="chip copy"
                onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
                title="Edit this copy"
              >
                {[o.completeness, o.condition].filter(Boolean).join(" · ") || "set condition…"}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeCopy(o.id);
                  }}
                  title="Remove this copy"
                >
                  <Icon id="x" />
                </button>
              </span>
            ))}
          </span>
        )}
      </span>
      <button className="ghost icon danger" onClick={del} title="Delete entry">
        <Icon id="trash" />
      </button>
      {editing !== null && (
        <span className="copy-edit">
          <select
            value={editVals.completeness}
            onChange={(e) => setEditVals({ ...editVals, completeness: e.target.value })}
          >
            {COMPLETENESS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <select
            value={editVals.condition}
            onChange={(e) => setEditVals({ ...editVals, condition: e.target.value })}
          >
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <button className="primary icon" onClick={saveEdit} disabled={busy} title="Save">
            <Icon id="check" />
          </button>
          <button className="ghost icon" onClick={() => setEditing(null)} title="Cancel">
            <Icon id="x" />
          </button>
        </span>
      )}
    </div>
  );
}
