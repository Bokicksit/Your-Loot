import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import BarcodeScan from "../components/BarcodeScan.jsx";
import { Icon } from "../components/Icons.jsx";
import { cleanTitle, detectEdition, detectFormat } from "../upc.js";

const FORMATS = ["4K UHD", "Blu-ray", "DVD", "VHS"];
const REGIONS = ["Region-free", "A", "B", "C", "1", "2", "3", "4"];
const CONDITIONS = ["Mint", "Good", "Fair", "Poor"];
const COMPLETENESS = ["loose", "CIB", "sealed"]; // loose = disc only

const EMPTY_FORM = {
  title: "",
  format: "Blu-ray",
  edition: "",
  region_code: "",
  image_url: null,
  tmdb_id: null,
  own: true,
  completeness: "CIB",
  condition: "Good",
};

export default function MoviesPage() {
  const [movies, setMovies] = useState([]);
  const [total, setTotal] = useState(0);
  const [formats, setFormats] = useState([]); // in-collection formats w/ counts
  const [search, setSearch] = useState("");
  const [formatFilter, setFormatFilter] = useState("");
  const [sort, setSort] = useState("title"); // title | format | added
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    const params = { sort };
    if (search) params.search = search;
    if (formatFilter) params.format = formatFilter;
    api
      .movies(params)
      .then((d) => {
        setMovies(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    api.movieFormats().then((fs) => {
      setFormats(fs);
      if (formatFilter && !fs.some((f) => f.format === formatFilter)) {
        setFormatFilter("");
      }
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, formatFilter, sort]);

  const tmdbSearch = async () => {
    if (form.title.trim().length < 2 || searching) return;
    setSearching(true);
    try {
      setResults(await api.tmdbSearch(form.title.trim()));
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  // barcode → product title → prefill fields → auto-run the TMDB search.
  // A movie UPC names the exact edition, so format/edition come along free.
  const onBarcode = async (code) => {
    try {
      const res = await api.barcodeLookup(code);
      if (!res.found) {
        alert("No product match for that barcode — type the title instead.");
        return;
      }
      const raw = res.titles[0].title;
      const title = cleanTitle(raw) || raw;
      setForm((f) => ({
        ...f,
        title,
        format: detectFormat(raw) || f.format,
        edition: detectEdition(raw) || f.edition,
        tmdb_id: null,
        image_url: null,
      }));
      setSearching(true);
      try {
        setResults(await api.tmdbSearch(title));
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
      tmdb_id: r.tmdb_id,
      image_url: r.poster_url,
    });
    setResults(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      const created = await api.addMovie({
        title: form.title,
        format: form.format || null,
        edition: form.edition.trim() || null,
        region_code: form.region_code || null,
        image_url: form.image_url,
        tmdb_id: form.tmdb_id,
      });
      if (form.own) {
        await api.addOwned(created.id, {
          condition: form.condition,
          completeness: form.completeness,
        });
      } else {
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

  const patchMovie = (id, status) =>
    setMovies((ms) =>
      ms.map((m) =>
        m.id === id ? { ...m, owned: status.owned, wanted: status.wanted } : m
      )
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search movies…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button
          className={showForm ? "ghost icon" : "primary"}
          onClick={() => setShowForm(!showForm)}
          title={showForm ? "Close" : "Add to shelf"}
        >
          <Icon id={showForm ? "x" : "plus"} />
          {!showForm && "Add"}
        </button>
      </div>

      <div className="chip-row">
        <button
          className={`chip ${formatFilter === "" ? "active" : ""}`}
          onClick={() => setFormatFilter("")}
        >
          All
        </button>
        {formats.map((f) => (
          <button
            key={f.format}
            className={`chip ${formatFilter === f.format ? "active" : ""}`}
            onClick={() => setFormatFilter(f.format)}
          >
            {f.format} ({f.count})
          </button>
        ))}
        <select
          className="chip-select"
          title="Sort"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          style={{ marginLeft: "auto" }}
        >
          <option value="title">A–Z</option>
          <option value="format">By format</option>
          <option value="added">Last added</option>
        </select>
      </div>

      {showForm && (
        <form className="add-form" onSubmit={submit}>
          <h2>Add to shelf</h2>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Title — then search TMDB"
              value={form.title}
              onChange={(e) =>
                // manual edits detach the TMDB link/poster
                setForm({ ...form, title: e.target.value, tmdb_id: null, image_url: null })
              }
              onKeyDown={(e) => {
                // Enter always searches — the form only submits via Add
                if (e.key === "Enter") {
                  e.preventDefault();
                  tmdbSearch();
                }
              }}
            />
            <button type="button" className="ghost" onClick={tmdbSearch} disabled={searching}>
              {searching ? "…" : "Search TMDB"}
            </button>
            <BarcodeScan onCode={onBarcode} />
          </div>
          <div className="form-row">
            <select
              value={form.format}
              onChange={(e) => setForm({ ...form, format: e.target.value })}
            >
              {FORMATS.map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
            <select
              value={form.region_code}
              onChange={(e) => setForm({ ...form, region_code: e.target.value })}
            >
              <option value="">Region…</option>
              {REGIONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Edition (Steelbook, Criterion, Director’s Cut…)"
              value={form.edition}
              onChange={(e) => setForm({ ...form, edition: e.target.value })}
            />
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
            {form.tmdb_id && (
              <span className="igdb-linked">
                <Icon id="link" />
                TMDB #{form.tmdb_id} linked
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
                  No TMDB matches.
                </li>
              )}
              {results.map((r) => (
                <li key={r.tmdb_id} onClick={() => pickResult(r)}>
                  {r.poster_url ? (
                    <img src={r.poster_url} alt="" loading="lazy" />
                  ) : (
                    <span className="placeholder" data-label="" />
                  )}
                  <span className="game-text">
                    <strong>{r.title}</strong>
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
      {!error && loaded && movies.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="disc" /></span>
          <strong>Shelf is empty</strong>
          <p>Hit Add and search TMDB, or enter discs by hand.</p>
        </div>
      )}

      <div className="game-list">
        {movies.map((m) => (
          <MovieRow key={m.id} movie={m} onChange={patchMovie} onDelete={load} />
        ))}
      </div>
    </div>
  );
}

function MovieRow({ movie, onChange, onDelete }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editVals, setEditVals] = useState({ completeness: "CIB", condition: "Good" });

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      const status = await fn();
      onChange(movie.id, status);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeCopy = (ownedId) => run(() => api.removeOwned(movie.id, ownedId));

  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      completeness: o.completeness || "CIB",
      condition: o.condition || "Good",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const status = await api.updateOwned(movie.id, editing, editVals);
      setEditing(null);
      return status;
    });

  const del = async () => {
    if (!confirm(`Delete "${movie.title}" and its records?`)) return;
    await api.deleteMovie(movie.id);
    onDelete();
  };

  return (
    <div className={`game-row ${movie.owned.length ? "row-owned" : ""}`}>
      {movie.image_url ? (
        <img className="game-cover" src={movie.image_url} alt="" loading="lazy" />
      ) : (
        <span className="game-icon"><Icon id="disc" /></span>
      )}
      <span className="game-text">
        <strong>{movie.title}</strong>
        <small className="game-meta">
          {[movie.attrs.format, movie.attrs.edition, movie.attrs.region_code]
            .filter(Boolean)
            .map((part) => (
              <span key={part}>{part}</span>
            ))}
        </small>
        {movie.owned.length > 0 && (
          <span className="copy-chips">
            {movie.owned.map((o) => (
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
