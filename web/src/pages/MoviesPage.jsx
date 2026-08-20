import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import ArtOptions from "../components/ArtOptions.jsx";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import HelpTip, { ShelfHelp } from "../components/HelpTip.jsx";
import { Icon } from "../components/Icons.jsx";
import { ShuffleButton } from "../components/Shuffle.jsx";
import { TagChips, TagEditor, TagFilter } from "../components/Tags.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { cleanTitle, detectEdition, detectFormat, firstHits, queryLadder } from "../upc.js";
import ViewToggle, {
  useTileView,
  useTileCols,
  useInlineDensity,
  TileDensity,
} from "../components/ViewToggle.jsx";
import { useListPref } from "../settings.jsx";

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
  tags: [],
  notes: "",
  tmdb_id: null,
  own: true,
  completeness: "CIB",
  condition: "Good",
};

// Shared wording, so every collection says this the same way. It is a notice,
// not a gate: a second copy of a game is an ordinary thing to own, and the
// only person who knows whether this one is a duplicate or a spare is holding
// it. Returns a sentence to show, or null.
async function duplicateNotice(scope, title) {
  if (!title.trim()) return null;
  let matches = [];
  try {
    ({ matches } = await api.duplicates(scope, title));
  } catch {
    return null; // the check failing must never be in anybody's way
  }
  if (!matches.length) return null;
  const m = matches[0];
  const copies = m.copies === 1 ? "1 copy" : `${m.copies} copies`;
  return (
    `You already have ${m.title}` +
    (m.detail ? ` — ${m.detail}` : "") +
    `, with ${copies}. Adding this makes another.`
  );
}

export default function MoviesPage() {
  const [movies, setMovies] = useState([]);
  const [total, setTotal] = useState(0);
  const [formats, setFormats] = useState([]); // in-collection formats w/ counts
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("movies");
  const [tileCols] = useTileCols("movies");
  const inlineDensity = useInlineDensity();
  const [formatFilter, setFormatFilter] = useListPref("movies", "formatFilter", "");
  const [tagFilter, setTagFilter] = useListPref("movies", "tagFilter", "");
  // bumped whenever tags change, so the filter re-reads its counts
  const [tagsChanged, setTagsChanged] = useState(0);
  const [sort, setSort] = useListPref("movies", "sort", "title"); // title | format | added
  // Shown while you fill the form in, not thrown at you on save.
  const [dupe, setDupe] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  // sort lives in the rail here rather than the sheet, and is not counted:
  // it never hides anything
  const activeFilters = [formatFilter, tagFilter].filter(Boolean).length;
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

  // Everything that narrows the list except what is typed. The dice takes
  // these and not the search box — filling that box is what a roll *does*, so
  // rolling from it would hand back the same item forever.
  const filters = { sort };
  if (tagFilter) filters.tag = tagFilter;
  if (formatFilter) filters.format = formatFilter;

  const load = () => {
    const params = { ...filters };
    if (search) params.search = search;
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
    if (!showForm) return setDupe(null);
    const t = setTimeout(
      () => duplicateNotice("movies", form.title).then(setDupe),
      350
    );
    return () => clearTimeout(t);
  }, [showForm, form.title]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, formatFilter, sort, tagFilter, tagsChanged]);

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
  // The artwork these lookups pick is a suggestion, and a suggestion should
  // stand aside for a better one. Tracking what we chose last lets a second
  // lookup replace it, while anything picked off the strip by hand is left
  // exactly where it is.
  const autoArt = useRef(null);
  // UPCitemdb's free tier is a hundred lookups a day and the format dropdown
  // is four options someone may well click through. Asking the same question
  // twice spends a lookup to receive an answer we already have.
  const lastLookup = useRef(null);

  const findCaseArt = async (title, format) => {
    const term = [cleanTitle(title) || title, format].filter(Boolean).join(" ");
    if (term.length < 3 || term === lastLookup.current) return;
    lastLookup.current = term;
    try {
      const { items } = await api.productSearch(term);
      const shots = (items || []).flatMap((i) => i.images).slice(0, 6);
      if (!shots.length) return;
      mergeArt(shots.map((url) => ({ url, kind: "box" })));
      // and take the slot off the poster — but never off something you chose
      setForm((f) => {
        const ours =
          !f.image_url ||
          /image\.tmdb\.org/i.test(f.image_url) ||
          f.image_url === autoArt.current;
        if (!ours) return f;
        autoArt.current = shots[0];
        return { ...f, image_url: shots[0] };
      });
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
    autoArt.current = null;
    lastLookup.current = null;
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
        notes: form.notes.trim() || null,
        tmdb_id: form.tmdb_id,
      });
      // after the create, because a tag needs something to hang on
      if (form.tags.length) {
        await api.setItemTags(created.id, "movies", form.tags);
        setTagsChanged((n) => n + 1);
      }
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
        m.id === id ? { ...m, owned: status.owned, wanted: status.wanted, tags: status.tags ?? movie.tags } : m
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
        {/* the magnifier and the count live inside the field, so the row
            spends its width on the field rather than on furniture */}
        <label className="searchbox">
          <Icon id="search" />
          <input
            type="search"
            placeholder="Search movies…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <span className="count">{total}</span>
        </label>
        <ShuffleButton fetcher={api.movies} params={filters} onPick={setSearch} noun="a film" />
        <button className="primary" onClick={openForm} title="Add to shelf">
          <Icon id="plus" />
          Add
        </button>
      </div>

      <div className="chip-row">
        {/* One button rather than a line that scrolls past the edge —
            the controls out of sight were never found. */}
        <button
          type="button"
          className={`chip ${activeFilters ? "active" : ""}`}
          onClick={() => setFiltersOpen(!filtersOpen)}
          aria-expanded={filtersOpen}
          title="Filters and sorting"
        >
          <Icon id="sliders" />
          Filters
          {activeFilters > 0 && <span className="chip-n">{activeFilters}</span>}
        </button>
        <span className="rail-spacer" />
        <ViewToggle module="movies" />
        {tiles && inlineDensity && <TileDensity module="movies" />}
        <ShelfHelp noun="a film" />
      </div>
      {filtersOpen && (
        <div className="filter-sheet">
          <label>
            <span>Format</span>
            <span className="sheet-chips">
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
            </span>
          </label>
          <label>
            <span>Sort</span>
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
          </label>
          <label>
            <span>Tag</span>
            <TagFilter
              scope="movies"
              value={tagFilter}
              onChange={setTagFilter}
              reloadKey={tagsChanged}
            />
          </label>
        </div>
      )}
      {/* its own row, not a chip in the rail — inside a line that
          scrolls sideways it slid under the filter beside it */}
      {tiles && !inlineDensity && <TileDensity module="movies" />}

      <AddSheet
        open={showForm && step === "search"}
        title="Find a film"
        onClose={closeForm}
        help={
          <>
            Type the title and <b>Search TMDB</b> brings back the film with
            its poster and year. The frame button scans the barcode on the
            case instead — that names the exact release, right down to the
            edition. <b>Enter it by hand</b> covers anything the databases
            don't carry.
          </>
        }
      >
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
        help={
          <>
            The <b>format</b> and <b>edition</b> boxes are what separate the
            DVD, the Blu-ray and the steelbook of the same film — three
            different objects on a shelf. <b>I own it</b> files your copy
            with completeness and condition; <b>I want it</b> puts it on the
            wanted list. Everything stays editable later.
          </>
        }
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
              onChange={(e) => {
                setForm({ ...form, format: e.target.value });
                // The case photo is per edition: the DVD, the Blu-ray and the
                // steelbook are three different objects with three different
                // covers. Until the format is named the search can only guess,
                // and it guesses Blu-ray — so naming it is exactly when the
                // right case becomes findable.
                findCaseArt(form.title, e.target.value);
              }}
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
          {dupe && <p className="dupe-note">{dupe}</p>}
          {/* last of the fields: a tag is what you think of once the rest
              is filled in */}
          <div className="form-row">
            <TagEditor
              scope="movies"
              value={form.tags}
              onChange={(tags) => setForm({ ...form, tags })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Note (optional)"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
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

      <div
        className={`game-list ${tiles ? `as-tiles cols-${tileCols}` : ""}`}
        style={tiles ? { "--tile-cols": tileCols } : undefined}
      >
        {movies.map((m) => (
          <MovieRow key={m.id} movie={m} onChange={patchMovie} onReload={load}
            onTagsChanged={() => setTagsChanged((n) => n + 1)} />
        ))}
      </div>
    </div>
  );
}

function MovieRow({ movie, onChange, onReload , onTagsChanged}) {
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
      tags: movie.tags || [],
      notes: movie.notes || "",
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
        notes: entry.notes.trim() || null,
      });
      // Staged with the rest of the form, so Cancel discards a tag the
      // same way it discards a retyped title.
      await api.setItemTags(movie.id, "movies", entry.tags);
      onTagsChanged?.();
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
          <TagChips tags={movie.tags} />
          {/* your own words about the thing, not about one copy */}
          {movie.notes && <p className="game-summary">{movie.notes}</p>}
          {movie.attrs.overview && (
            <p className="game-summary">{movie.attrs.overview}</p>
          )}
        </span>
      )}
      {entryOpen && (
        <span className="entry-edit">
          <span className="game-info-line">
            Release details
            <HelpTip>
              This edits the <b>entry</b> — the release itself: title,
              format, edition, poster. It doesn't touch what you own. Your
              copy — sealed, CIB, loose, its condition — lives on the small
              chip on the row, and the trash button deletes the whole entry.
            </HelpTip>
          </span>
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
          </div>
          <div className="form-row">
            <TagEditor
              scope="movies"
              id={movie.id}
              value={entry.tags}
              onChange={(tags) => setEntry({ ...entry, tags })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Note (optional)"
              value={entry.notes}
              onChange={(e) => setEntry({ ...entry, notes: e.target.value })}
            />
          </div>
          <div className="form-row">
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
