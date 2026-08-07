import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import ArtOptions from "../components/ArtOptions.jsx";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { Icon } from "../components/Icons.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { cleanTitle, detectEdition, detectFormat, firstHits, queryLadder } from "../upc.js";
import ViewToggle, { useTileView } from "../components/ViewToggle.jsx";

const FORMATS = ["4K UHD", "Blu-ray", "DVD", "VHS"];
const REGIONS = ["Region-free", "A", "B", "C", "1", "2", "3", "4"];
const GENRES = [
  "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
  "Drama", "Family", "Fantasy", "History", "Horror", "Music", "Mystery",
  "Romance", "Sci-Fi", "Thriller", "War", "Western",
];
const CONDITIONS = ["Mint", "Good", "Fair", "Poor"];
const COMPLETENESS = ["loose", "CIB", "sealed"]; // loose = disc only

const EMPTY_FORM = {
  title: "",
  format: "Blu-ray",
  edition: "",
  region_code: "",
  genre: "",
  overview: null,
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
  const [tiles] = useTileView("movies");
  const [formatFilter, setFormatFilter] = useState("");
  const [sort, setSort] = useState("title"); // title | format | added
  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState("search"); // search -> details
  const [form, setForm] = useState(EMPTY_FORM);
  const [results, setResults] = useState(null);
  const [art, setArt] = useState([]); // artwork candidates: case photos + poster
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  // keep one entry per url, case photos first — they're the edition you own
  const mergeArt = (extra) =>
    setArt((prev) => {
      const seen = new Set(prev.map((a) => a.url));
      return [...prev, ...extra.filter((a) => a.url && !seen.has(a.url))];
    });

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
    setResults(null); // clear the old hits so the status stands alone
    try {
      // cleanTitle so "Alien 4K UHD Steelbook" typed by hand searches for
      // "Alien", the same as a scanned product title does
      const typed = cleanTitle(form.title) || form.title;
      setResults(await firstHits(queryLadder(typed), (q) => api.tmdbSearch(q)));
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
      // retailer photos of the actual case — better than a poster for a
      // physical shelf, so the sharpest one is selected up front
      const boxArt = (res.titles[0].images || []).map((url) => ({ url, kind: "box" }));
      setArt(boxArt);
      setForm((f) => ({
        ...f,
        title,
        format: detectFormat(raw) || f.format,
        edition: detectEdition(raw) || f.edition,
        tmdb_id: null,
        image_url: boxArt[0]?.url || null,
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

  // TMDB has no case art — 229 posters for one film and every one a 2:3
  // theatrical poster — so the picture of the thing on your shelf has to come
  // from a shop listing. Runs on an explicit pick, never on a keystroke: it
  // shares the barcode service's daily budget.
  const findCaseArt = async (title, format) => {
    const term = [cleanTitle(title) || title, format].filter(Boolean).join(" ");
    if (term.length < 3) return;
    try {
      const { items } = await api.productSearch(term);
      const shots = (items || []).flatMap((i) => i.images).slice(0, 6);
      if (!shots.length) return;
      mergeArt(shots.map((url) => ({ url, kind: "box" })));
      // and take the slot off the poster — but never off something you chose
      setForm((f) => ({
        ...f,
        image_url:
          !f.image_url || /image\.tmdb\.org/i.test(f.image_url) ? shots[0] : f.image_url,
      }));
    } catch {
      /* artwork is a bonus; an entry saves fine without it */
    }
  };

  const pickResult = (r) => {
    if (r.poster_url) mergeArt([{ url: r.poster_url, kind: "poster" }]);
    setForm({
      ...form,
      title: r.year ? `${r.title} (${r.year})` : r.title,
      tmdb_id: r.tmdb_id,
      // a case photo from the barcode already shows the edition you own, so
      // the poster only fills in when there's nothing better
      image_url: form.image_url || r.poster_url,
      genre: r.genre || form.genre,
      overview: r.overview || null,
    });
    setResults(null);
    setStep("details"); // picked a film — on to describing your copy
    findCaseArt(r.title, form.format);
  };

  const openForm = () => {
    setForm(EMPTY_FORM);
    setArt([]);
    setResults(null);
    setStep("search");
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
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
        genre: form.genre || null,
        overview: form.overview,
        image_url: await api.localiseImage(form.image_url),
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
      setArt([]);
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

  const resultsList = results && (
    <ul className="igdb-results">
      {results.length === 0 && (
        <li style={{ cursor: "default", color: "var(--text-mute)" }}>No TMDB matches.</li>
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
        <button className="primary" onClick={openForm} title="Add to shelf">
          <Icon id="plus" />
          Add
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
          <option value="year">By year</option>
          <option value="added">Last added</option>
          <option value="oldest">First added</option>
        </select>
        <ViewToggle module="movies" />
      </div>

      <AddSheet open={showForm && step === "search"} title="Find a film" onClose={closeForm}>
        <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Title — then search TMDB"
              value={form.title}
              onChange={(e) =>
                // manual edits detach the TMDB link/poster/overview
                setForm({
                  ...form,
                  title: e.target.value,
                  tmdb_id: null,
                  image_url: null,
                  overview: null,
                })
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
        {searching && <Searching />}
        {resultsList}
        <ByHand onClick={() => setStep("details")} />
      </AddSheet>

      <AddSheet
        open={showForm && step === "details"}
        title="Add to shelf"
        onClose={closeForm}
        onBack={() => setStep("search")}
      >
        <form className="add-form" onSubmit={submit}>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Title as you want it filed"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
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
            <select
              title="Genre"
              value={form.genre}
              onChange={(e) => setForm({ ...form, genre: e.target.value })}
            >
              <option value="">Genre…</option>
              {GENRES.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </div>
          <ArtOptions
            options={art}
            value={form.image_url}
            onChange={(url) => setForm({ ...form, image_url: url })}
          />
          <div className="form-row">
            <ImagePicker
              value={form.image_url}
              label="Cover photo"
              onChange={(url) => setForm({ ...form, image_url: url })}
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
        </form>
      </AddSheet>

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

      <div className={`game-list ${tiles ? "as-tiles" : ""}`}>
        {movies.map((m) => (
          <MovieRow key={m.id} movie={m} onChange={patchMovie} onReload={load} />
        ))}
      </div>
    </div>
  );
}

function MovieRow({ movie, onChange, onReload }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editVals, setEditVals] = useState({ completeness: "CIB", condition: "Good" });
  const [entryOpen, setEntryOpen] = useState(false); // entry (catalog) editor
  const [entry, setEntry] = useState({});
  const [infoOpen, setInfoOpen] = useState(false); // expandable detail card
  const rowRef = useRef(null);
  const entryInit = useRef(null); // what the editor opened with, to spot edits
  useDismiss(
    infoOpen || entryOpen || editing !== null,
    () => {
      setInfoOpen(false);
      setEntryOpen(false);
      setEditing(null);
    },
    [rowRef],
    () => keepOpen(entry, entryInit.current, entryOpen, movie.title),
  );

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

  const removeCopy = (o) => {
    const label = [o.completeness, o.condition].filter(Boolean).join(" · ") || "copy";
    if (!confirm(`Remove this copy of ${movie.title} (${label})?`)) return;
    run(() => api.removeOwned(movie.id, o.id));
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
      const status = await api.updateOwned(movie.id, editing, editVals);
      setEditing(null);
      return status;
    });

  const openEntry = () => {
    const vals = {
      title: movie.title,
      format: movie.attrs.format || "Blu-ray",
      edition: movie.attrs.edition || "",
      region_code: movie.attrs.region_code || "",
      genre: movie.attrs.genre || "",
      image_url: movie.image_url,
    };
    entryInit.current = vals;
    setEntry(vals);
    setEntryOpen(true);
  };

  const saveEntry = async () => {
    if (busy || !entry.title.trim()) return;
    setBusy(true);
    try {
      await api.updateMovie(movie.id, {
        title: entry.title.trim(),
        format: entry.format || null,
        edition: entry.edition.trim() || null,
        region_code: entry.region_code || null,
        genre: entry.genre || null,
        image_url: await api.localiseImage(entry.image_url),
      });
      setEntryOpen(false);
      onReload();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (!confirm(`Delete "${movie.title}" and its records?`)) return;
    await api.deleteMovie(movie.id);
    onReload();
  };

  return (
    <div
      ref={rowRef}
      className={`game-row ${movie.owned.length ? "row-owned" : ""} ${infoOpen || entryOpen ? "open" : ""}`}
    >
      {movie.image_url ? (
        <img
          className="game-cover"
          src={movie.image_url}
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
          <Icon id="disc" />
        </span>
      )}
      <span
        className="game-text"
        style={{ cursor: "pointer" }}
        onClick={() => setInfoOpen(!infoOpen)}
      >
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
                <Icon id="pencil" />
                {[o.completeness, o.condition].filter(Boolean).join(" · ") || "set condition…"}
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
            {movie.image_url && (
              <img className="expand-cover" src={movie.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{movie.title}</span>
              <span className="expand-sub">
                {[
                  movie.attrs.format,
                  movie.attrs.edition,
                  movie.attrs.region_code && `Region ${movie.attrs.region_code}`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
              {movie.attrs.genre && (
                <span className="game-info-line">{movie.attrs.genre}</span>
              )}
            </div>
            {/* a steelbook and a plain case of the same film are different
                items at very different prices */}
            <EbayLink
              title={movie.title}
              terms={[movie.attrs.format, movie.attrs.edition]}
            />
          </div>
          {movie.attrs.overview && (
            <p className="game-summary">{movie.attrs.overview}</p>
          )}
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
              value={entry.format}
              onChange={(e) => setEntry({ ...entry, format: e.target.value })}
            >
              {FORMATS.map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
            <select
              value={entry.region_code}
              onChange={(e) => setEntry({ ...entry, region_code: e.target.value })}
            >
              <option value="">Region…</option>
              {REGIONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
            <select
              value={entry.genre}
              onChange={(e) => setEntry({ ...entry, genre: e.target.value })}
            >
              <option value="">Genre…</option>
              {GENRES.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Edition"
              value={entry.edition}
              onChange={(e) => setEntry({ ...entry, edition: e.target.value })}
            />
            <ImagePicker
              value={entry.image_url}
              label="Case photo"
              onChange={(url) => setEntry({ ...entry, image_url: url })}
            />
            <button
              className="primary icon"
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
