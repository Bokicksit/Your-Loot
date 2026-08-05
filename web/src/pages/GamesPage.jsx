import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import BarcodeScan from "../components/BarcodeScan.jsx";
import { Icon } from "../components/Icons.jsx";
import { cleanGameTitle, stripPublisherPrefix } from "../upc.js";
import { GAME_COMPLETENESS, labelFor, withUnknown } from "../vocab.js";

const REGIONS = ["NTSC-U", "PAL", "NTSC-J", "Region-free"];
const CONDITIONS = ["Mint", "Good", "Fair", "Poor"];

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
  // info-panel metadata, filled by an IGDB pick
  summary: null,
  release_year: null,
  genres: null,
  developer: null,
  publisher: null,
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
    // theirs contains ours ("…Entertainment System" ⊃ "Super Nintendo"):
    // longest of ours wins. Ours contains theirs ("Nintendo Wii" ⊃ "Wii"):
    // shortest of ours wins — "Wii" must not match "Nintendo Wii U".
    const contained = platforms
      .filter((p) => n.includes(p.name.toLowerCase()))
      .sort((a, b) => b.name.length - a.name.length)[0];
    if (contained) return contained.id;
    const containing = platforms
      .filter((p) => p.name.toLowerCase().includes(n))
      .sort((a, b) => a.name.length - b.name.length)[0];
    if (containing) return containing.id;
  }
  return "";
}

// all our platform ids a game was released on (for restricting the dropdown)
function matchAllPlatforms(igdbNames, platforms) {
  const ids = new Set();
  for (const name of igdbNames) {
    const id = matchPlatform([name], platforms);
    if (id) ids.add(id);
  }
  return [...ids];
}

export default function GamesPage() {
  const [games, setGames] = useState([]);
  const [total, setTotal] = useState(0);
  const [platforms, setPlatforms] = useState([]);
  const [search, setSearch] = useState("");
  const [platformFilter, setPlatformFilter] = useState(""); // system; genre later
  const [usedPlatforms, setUsedPlatforms] = useState([]); // only what's in the collection
  const [sort, setSort] = useState("title"); // title | platform | added
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [results, setResults] = useState(null); // null = no search yet
  const [allowedPlatforms, setAllowedPlatforms] = useState([]); // from IGDB pick
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.platforms().then(setPlatforms);
  }, []);

  const load = () => {
    // hardware lives on its own tab now — this page is games only
    const params = { sort, is_hardware: false };
    if (search) params.search = search;
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
  }, [search, platformFilter, sort]);

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
        // fallback ladder: full title first (protects titles that genuinely
        // start with a publisher), then publisher-prefix stripped, then
        // trailing words dropped — stop at the first query with results
        const queries = [title];
        const pre = stripPublisherPrefix(title);
        if (pre && pre !== title) queries.push(pre);
        let words = (pre || title).split(" ");
        while (words.length > 2 && queries.length < 5) {
          words = words.slice(0, -1);
          queries.push(words.join(" "));
        }
        let found = [];
        for (const q of queries) {
          found = await api.igdbSearch(q);
          if (found.length) break;
        }
        setResults(found);
      } finally {
        setSearching(false);
      }
    } catch (e) {
      alert(e.message);
    }
  };

  const pickResult = (r) => {
    // restrict the platform dropdown to systems this game shipped on
    const allowed = matchAllPlatforms(r.platforms, platforms);
    setAllowedPlatforms(allowed);
    setForm({
      ...form,
      title: r.year ? `${r.title} (${r.year})` : r.title,
      igdb_id: r.igdb_id,
      image_url: r.cover_url, // IGDB cover = box art
      platform_id: matchPlatform(r.platforms, platforms) || "",
      summary: r.summary || null,
      release_year: r.year ? Number(r.year) : null,
      genres: r.genres?.length ? r.genres.join(", ") : null,
      developer: r.developer || null,
      publisher: r.publisher || null,
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
        summary: form.summary,
        release_year: form.release_year,
        genres: form.genres,
        developer: form.developer,
        publisher: form.publisher,
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
      setAllowedPlatforms([]);
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
              onChange={(e) => {
                // manual edits detach the IGDB link/cover/metadata
                setForm({
                  ...form,
                  title: e.target.value,
                  igdb_id: null,
                  image_url: null,
                  summary: null,
                  release_year: null,
                  genres: null,
                  developer: null,
                  publisher: null,
                });
                setAllowedPlatforms([]);
              }}
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
              {(form.igdb_id && allowedPlatforms.length > 0
                ? platforms.filter((p) => allowedPlatforms.includes(p.id))
                : platforms
              ).map((p) => (
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
              title="What you have"
              disabled={!form.own}
              value={form.completeness}
              onChange={(e) => setForm({ ...form, completeness: e.target.value })}
            >
              {GAME_COMPLETENESS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
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
          <GameRow
            key={g.id}
            game={g}
            platforms={platforms}
            onChange={patchGame}
            onReload={load}
          />
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

function GameRow({ game, platforms, onChange, onReload }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // owned id being edited
  const [editVals, setEditVals] = useState({ completeness: "CIB", condition: "Good" });
  const [entryOpen, setEntryOpen] = useState(false); // entry (catalog) editor
  const [entry, setEntry] = useState({});
  const [infoOpen, setInfoOpen] = useState(false); // expandable detail card

  const a = game.attrs;
  const infoLine = [
    a.release_year,
    a.genres,
    a.developer && `Dev: ${a.developer}`,
    a.publisher && a.publisher !== a.developer && `Pub: ${a.publisher}`,
  ]
    .filter(Boolean)
    .join("  ·  ");

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

  const copyLabel = (o) =>
    [o.completeness && labelFor(GAME_COMPLETENESS, o.completeness), o.condition]
      .filter(Boolean)
      .join(" · ");

  const removeCopy = (o) => {
    if (!confirm(`Remove this copy of ${game.title} (${copyLabel(o) || "copy"})?`)) return;
    run(() => api.removeOwned(game.id, o.id));
  };

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
  const openEntry = () => {
    setEntry({
      title: game.title,
      platform_id: game.attrs.platform_id ? String(game.attrs.platform_id) : "",
      region: game.attrs.region || "",
      is_hardware: game.attrs.is_hardware,
    });
    setEntryOpen(true);
  };

  const saveEntry = async () => {
    if (busy || !entry.title.trim()) return;
    setBusy(true);
    try {
      await api.updateGame(game.id, {
        title: entry.title.trim(),
        platform_id: entry.platform_id ? Number(entry.platform_id) : null,
        region: entry.region || null,
        is_hardware: entry.is_hardware,
      });
      setEntryOpen(false);
      onReload(); // re-fetch: sort order and filter counts may have changed
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  // no want-star here: wanting happens at add time ("I want it") and is
  // managed on the Wanted tab — library rows are for owned copies
  const del = async () => {
    if (!confirm(`Delete "${game.title}" and its records?`)) return;
    await api.deleteGame(game.id);
    onReload();
  };

  return (
    <div className={`game-row ${game.owned.length ? "row-owned" : ""}`}>
      {game.image_url ? (
        <img
          className="game-cover"
          src={game.image_url}
          alt=""
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={() => setInfoOpen(!infoOpen)}
        />
      ) : (
        <span
          className="game-icon"
          style={{ cursor: "pointer" }}
          onClick={() => setInfoOpen(!infoOpen)}
        >
          <Icon id={game.attrs.is_hardware ? "pad" : "disc"} />
        </span>
      )}
      <span
        className="game-text"
        style={{ cursor: "pointer" }}
        onClick={() => setInfoOpen(!infoOpen)}
      >
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
                {copyLabel(o) || "set condition…"}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeCopy(o);
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
      <span className="row-buttons">
        <button
          className="ghost icon"
          onClick={() => (entryOpen ? setEntryOpen(false) : openEntry())}
          title="Edit entry"
        >
          <Icon id="pencil" />
        </button>
        <button className="ghost icon danger" onClick={del} title="Delete entry">
          <Icon id="trash" />
        </button>
      </span>
      {infoOpen && (
        <span className="entry-edit game-info">
          <div className="expand-card">
            {game.image_url && (
              <img className="expand-cover" src={game.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{game.title}</span>
              <span className="expand-sub">
                {[a.platform_name, a.region, a.is_hardware && "Hardware"]
                  .filter(Boolean)
                  .join(" · ") || "No system set"}
              </span>
              {infoLine && <span className="game-info-line">{infoLine}</span>}
            </div>
          </div>
          {a.summary && <p className="game-summary">{a.summary}</p>}
        </span>
      )}
      {entryOpen && (
        <span className="entry-edit">
          <div className="form-row">
            <input
              type="text"
              className="grow"
              value={entry.title}
              onChange={(e) => setEntry({ ...entry, title: e.target.value })}
            />
          </div>
          <div className="form-row">
            <select
              value={entry.platform_id}
              onChange={(e) => setEntry({ ...entry, platform_id: e.target.value })}
            >
              <option value="">Platform…</option>
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <select
              value={entry.region}
              onChange={(e) => setEntry({ ...entry, region: e.target.value })}
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
              className={`toggle ${entry.is_hardware ? "on" : ""}`}
              onClick={() => setEntry({ ...entry, is_hardware: !entry.is_hardware })}
            >
              Hardware
            </button>
            <button
              className="primary icon"
              style={{ marginLeft: "auto" }}
              onClick={saveEntry}
              disabled={busy}
              title="Save"
            >
              <Icon id="check" />
            </button>
            <button className="ghost icon" onClick={() => setEntryOpen(false)} title="Cancel">
              <Icon id="x" />
            </button>
          </div>
        </span>
      )}
      {editing !== null && (
        <span className="copy-edit">
          <select
            title="What you have"
            value={editVals.completeness}
            onChange={(e) => setEditVals({ ...editVals, completeness: e.target.value })}
          >
            {withUnknown(GAME_COMPLETENESS, editVals.completeness).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
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
