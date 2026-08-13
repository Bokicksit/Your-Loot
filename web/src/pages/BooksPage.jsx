import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import ArtOptions from "../components/ArtOptions.jsx";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { Icon } from "../components/Icons.jsx";
import { TagChips, TagEditor, TagFilter } from "../components/Tags.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import ViewToggle, { useTileView, useTileCols, TileDensity } from "../components/ViewToggle.jsx";
import { useListPref, useSettings } from "../settings.jsx";

// Graphic Novel and Omnibus sit here rather than in Comics because that's
// where the barcode puts them: a collected edition carries an ISBN, which Open
// Library resolves, while Comic Vine indexes single issues and no barcodes at
// all. Filter Books by one of these and sort By series and you have the
// graphic-novel shelf, in reading order. Manga volumes land the same way.
const FORMATS = [
  "Hardcover",
  "Paperback",
  "Trade Paperback",
  "Mass Market",
  "Graphic Novel",
  "Omnibus",
  "Leather",
  "Audiobook",
];
// book grading is its own vocabulary — collectors don't say "Mint"
const CONDITIONS = ["Fine", "Near Fine", "Very Good", "Good", "Fair", "Poor"];
// on a book, "completeness" is really about the jacket and provenance
const COMPLETENESS = ["With jacket", "No jacket", "Ex-library", "Signed"];

const EMPTY_FORM = {
  title: "",
  author: "",
  publisher: "",
  isbn: "",
  format: "Paperback",
  edition: "",
  publish_year: "",
  page_count: "",
  series: "",
  blurb: null,
  image_url: null,
  tags: [],
  notes: "",
  own: true,
  completeness: "With jacket",
  condition: "Very Good",
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

export default function BooksPage() {
  const { settings } = useSettings();
  // A shelf leans one way — mostly hardbacks with jackets, or mostly
  // paperbacks — so the two fields nobody changes get answered once in
  // Settings instead of on every book.
  const blankBook = () => ({
    ...EMPTY_FORM,
    format: settings?.default_book_format || EMPTY_FORM.format,
    completeness: settings?.default_book_jacket || EMPTY_FORM.completeness,
  });
  const [books, setBooks] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({ authors: [], formats: [] });
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("books");
  const [tileCols] = useTileCols("books");
  const [authorFilter, setAuthorFilter] = useListPref("books", "authorFilter", "");
  const [formatFilter, setFormatFilter] = useListPref("books", "formatFilter", "");
  const [tagFilter, setTagFilter] = useListPref("books", "tagFilter", "");
  // bumped whenever tags change, so the filter re-reads its counts
  const [tagsChanged, setTagsChanged] = useState(0);
  const [sort, setSort] = useListPref("books", "sort", "title");
  // Shown while you fill the form in, not thrown at you on save.
  const [dupe, setDupe] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState("search"); // search -> details
  const [form, setForm] = useState(EMPTY_FORM);
  const [art, setArt] = useState([]); // retailer photos of the actual package
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  // one entry per url, newest kept out of the way of what is already there
  const mergeArt = (extra) =>
    setArt((prev) => {
      const seen = new Set(prev.map((a) => a.url));
      return [...prev, ...extra.filter((a) => a.url && !seen.has(a.url))];
    });

  const load = () => {
    const params = { sort };
    if (search) params.search = search;
    if (tagFilter) params.tag = tagFilter;
    if (authorFilter) params.author = authorFilter;
    if (formatFilter) params.format = formatFilter;
    api
      .books(params)
      .then((d) => {
        setBooks(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    api.bookFacets().then((f) => {
      setFacets(f);
      if (authorFilter && !f.authors.some((a) => a.author === authorFilter)) setAuthorFilter("");
      if (formatFilter && !f.formats.some((x) => x.format === formatFilter)) setFormatFilter("");
    });
  };

  useEffect(() => {
    if (!showForm) return setDupe(null);
    const t = setTimeout(
      () => duplicateNotice("books", form.title).then(setDupe),
      350
    );
    return () => clearTimeout(t);
  }, [showForm, form.title]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, authorFilter, formatFilter, sort, tagFilter, tagsChanged]);

  const lookup = async (params) => {
    setSearching(true);
    setResults(null); // clear the old hits so the status stands alone
    try {
      setResults(await api.openLibrarySearch(params));
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  // the ISBN barcode on the back of a book resolves in a single call
  const onBarcode = (code) => lookup({ isbn: code });

  // Title and author together is the precise query, but Open Library indexes
  // plenty of editions without a usable author string, so a miss falls back to
  // the title on its own rather than reporting nothing found.
  const textSearch = async () => {
    const title = form.title.trim();
    const author = form.author.trim();
    const q = [title, author].filter(Boolean).join(" ");
    if (q.length < 2) return;
    setSearching(true);
    setResults(null);
    try {
      let hits = await api.openLibrarySearch({ q });
      if (!hits?.length && author && title) hits = await api.openLibrarySearch({ q: title });
      setResults(hits || []);
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  const CATALOG_ART = /covers\.openlibrary\.org/i;
  const lastLookup = useRef(null);
  const autoArt = useRef(null);

  // Retailer photographs of the actual package, the same ones a barcode scan
  // brings back. A catalogue picture is the publisher's artwork; a shop
  // listing is somebody's photo of the thing in a box — which is what you
  // own, and often the only way to tell one edition from another.
  //
  // Only ever offered, never forced: it takes the slot from a catalogue image
  // or from its own last suggestion, and leaves anything you picked alone.
  const findRetailArt = async (...parts) => {
    const term = parts.filter(Boolean).join(" ").trim();
    if (term.length < 3 || term === lastLookup.current) return;
    lastLookup.current = term;
    try {
      const { items } = await api.productSearch(term);
      const shots = (items || []).flatMap((i) => i.images).slice(0, 6);
      if (!shots.length) return;
      mergeArt(shots.map((url) => ({ url, kind: "box" })));
      setForm((f) => {
        const ours =
          !f.image_url || CATALOG_ART.test(f.image_url) || f.image_url === autoArt.current;
        if (!ours) return f;
        autoArt.current = shots[0];
        return { ...f, image_url: shots[0] };
      });
    } catch {
      /* artwork is a bonus; an entry saves fine without it */
    }
  };

  const pickResult = (r) => {
    setForm((f) => ({
      ...f,
      title: r.title || f.title,
      author: r.author || "",
      publisher: r.publisher || "",
      isbn: r.isbn || "",
      publish_year: r.publish_year || "",
      page_count: r.page_count || "",
      image_url: r.image_url || null,
      blurb: null,
    }));
    findRetailArt(r.title);
    setResults(null);
    setStep("details"); // picked an edition — on to describing your copy
    // The blurb is a second request and often a miss, so the form opens
    // without waiting and fills itself in if one turns up.
    if (r.olid) {
      api
        .bookDescription(r.olid)
        .then(({ description }) =>
          description && setForm((f) => ({ ...f, blurb: description }))
        )
        .catch(() => {}); // no blurb is the normal case, not an error
    }
  };

  const openForm = () => {
    setForm(blankBook());
    setResults(null);
    // last time's shop photos are about last time's thing
    setArt([]);
    lastLookup.current = null;
    autoArt.current = null;
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
      const created = await api.addBook({
        title: form.title,
        author: form.author.trim() || null,
        publisher: form.publisher.trim() || null,
        isbn: form.isbn.trim() || null,
        format: form.format || null,
        edition: form.edition.trim() || null,
        publish_year: form.publish_year ? Number(form.publish_year) : null,
        page_count: form.page_count ? Number(form.page_count) : null,
        series: form.series.trim() || null,
        // a jacket borrowed from a shop listing outlives the listing this way;
        // Open Library's own covers are stable and stay linked
        image_url: await api.localiseImage(form.image_url),
        notes: form.notes.trim() || null,
        blurb: form.blurb || null,
      });
      // after the create, because a tag needs something to hang on
      if (form.tags.length) {
        await api.setItemTags(created.id, "books", form.tags);
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
      setForm(blankBook());
      setResults(null);
      setShowForm(false);
      if (wantMode) navigate("/wanted");
      else load();
    } catch (err) {
      alert(err.message);
    }
  };

  const patchBook = (id, status) =>
    setBooks((bs) =>
      bs.map((b) => (b.id === id ? { ...b, owned: status.owned, wanted: status.wanted, tags: status.tags ?? book.tags } : b))
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
            placeholder="Search title or author…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <span className="count">{total}</span>
        </label>
        <button className="primary" onClick={openForm} title="Add a book">
          <Icon id="plus" />
          Add
        </button>
      </div>

      <div className="chip-row">
        {facets.formats.length > 0 && (
          <select
            className="chip-select"
            value={formatFilter}
            onChange={(e) => setFormatFilter(e.target.value)}
          >
            <option value="">All formats</option>
            {facets.formats.map((f) => (
              <option key={f.format} value={f.format}>
                {f.format} ({f.count})
              </option>
            ))}
          </select>
        )}
        {facets.authors.length > 0 && (
          <select
            className="chip-select"
            value={authorFilter}
            onChange={(e) => setAuthorFilter(e.target.value)}
          >
            <option value="">All authors</option>
            {facets.authors.map((a) => (
              <option key={a.author} value={a.author}>
                {a.author} ({a.count})
              </option>
            ))}
          </select>
        )}
        <TagFilter
          scope="books"
          value={tagFilter}
          onChange={setTagFilter}
          reloadKey={tagsChanged}
        />
        <select
          className="chip-select"
          title="Sort"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          style={{ marginLeft: "auto" }}
        >
          <option value="title">A–Z</option>
          <option value="author">By author</option>
          <option value="series">By series</option>
          <option value="year">By year</option>
          <option value="added">Last added</option>
          <option value="oldest">First added</option>
        </select>
        <ViewToggle module="books" />
      </div>
      {/* its own row, not a chip in the rail — inside a line that
          scrolls sideways it slid under the filter beside it */}
      {tiles && <TileDensity module="books" />}

      <AddSheet open={showForm && step === "search"} title="Find a book" onClose={closeForm}>
        <div className="form-row">
          <input
            type="text"
            className="grow"
            autoFocus
            placeholder="Title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), textSearch())}
          />
          <BarcodeScan onCode={onBarcode} />
        </div>
        <div className="form-row">
          <input
            type="text"
            className="grow"
            placeholder="Author"
            value={form.author}
            onChange={(e) => setForm({ ...form, author: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), textSearch())}
          />
          <button type="button" className="ghost" onClick={textSearch} disabled={searching}>
            {searching ? "…" : "Look up"}
          </button>
        </div>
        {searching && <Searching />}
        {results && (
            <>
              <span className="game-info-line">
                Open Library · {results.length} match{results.length === 1 ? "" : "es"}
              </span>
              {results.length === 0 && (
                <p className="empty" style={{ padding: "var(--s-3)" }}>
                  Nothing found — fill the details in by hand below.
                </p>
              )}
              <div className="grid pick-grid">
                {results.map((r, i) => (
                  <div
                    key={r.olid || i}
                    className="tile pick"
                    onClick={() => pickResult(r)}
                    title="Use this edition"
                  >
                    {r.image_url ? (
                      <img src={r.image_url} alt={r.title} loading="lazy" />
                    ) : (
                      <div className="placeholder" data-label="no cover" />
                    )}
                    <div className="tile-info">
                      <strong>{r.title}</strong>
                      <small>{r.author || "—"}</small>
                      <small>{r.publish_year || ""}</small>
                    </div>
                  </div>
                ))}
              </div>
          </>
        )}
        <ByHand onClick={() => setStep("details")} />
      </AddSheet>

      <AddSheet
        open={showForm && step === "details"}
        title="Add a book"
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
            <input
              type="text"
              className="grow"
              placeholder="Author"
              value={form.author}
              onChange={(e) => setForm({ ...form, author: e.target.value })}
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
            <input
              type="text"
              style={{ maxWidth: "120px" }}
              placeholder="Year"
              inputMode="numeric"
              value={form.publish_year}
              onChange={(e) => setForm({ ...form, publish_year: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Edition (First, Folio…)"
              value={form.edition}
              onChange={(e) => setForm({ ...form, edition: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Series (optional)"
              value={form.series}
              onChange={(e) => setForm({ ...form, series: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "170px" }}
              placeholder="ISBN"
              value={form.isbn}
              onChange={(e) => setForm({ ...form, isbn: e.target.value })}
            />
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
              scope="books"
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
          <div className="form-row wrap">
            <button
              type="button"
              className={`toggle ${form.own ? "on" : ""}`}
              onClick={() => setForm({ ...form, own: !form.own })}
            >
              {form.own ? "I own it" : "I want it"}
            </button>
            <select
              disabled={!form.own}
              title="Jacket / provenance"
              value={form.completeness}
              onChange={(e) => setForm({ ...form, completeness: e.target.value })}
            >
              {COMPLETENESS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <select
              disabled={!form.own}
              title="Condition"
              value={form.condition}
              onChange={(e) => setForm({ ...form, condition: e.target.value })}
            >
              {CONDITIONS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
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
      {!error && loaded && books.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="book" /></span>
          <strong>No books yet</strong>
          <p>Scan the barcode on the back of a book, or search by title.</p>
        </div>
      )}

      <div
        className={`game-list ${tiles ? `as-tiles cols-${tileCols}` : ""}`}
        style={tiles ? { "--tile-cols": tileCols } : undefined}
      >
        {books.map((b) => (
          <BookRow key={b.id} book={b} onChange={patchBook} onReload={load}
            onTagsChanged={() => setTagsChanged((n) => n + 1)} />
        ))}
      </div>
    </div>
  );
}

function BookRow({ book, onChange, onReload , onTagsChanged}) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editVals, setEditVals] = useState({ completeness: "With jacket", condition: "Very Good" });
  const [infoOpen, setInfoOpen] = useState(false);
  const a = book.attrs;

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      onChange(book.id, await fn());
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeCopy = (o) => {
    const label = [o.completeness, o.condition].filter(Boolean).join(" · ") || "copy";
    if (!confirm(`Remove this copy of ${book.title} (${label})?`)) return;
    run(() => api.removeOwned(book.id, o.id));
  };
  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      completeness: o.completeness || "With jacket",
      condition: o.condition || "Very Good",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const s = await api.updateOwned(book.id, editing, editVals);
      setEditing(null);
      return s;
    });

  const del = async () => {
    if (!confirm(`Delete "${book.title}" and its records?`)) return;
    await api.deleteBook(book.id);
    onReload();
  };

  const [entry, setEntry] = useState(null); // null = editor closed
  const rowRef = useRef(null);
  const entryInit = useRef(null); // what the editor opened with, to spot edits
  useDismiss(
    infoOpen || entry !== null || editing !== null,
    () => {
      setInfoOpen(false);
      setEntry(null);
      setEditing(null);
    },
    [rowRef],
    () => keepOpen(entry, entryInit.current, entry !== null, book.title),
  );
  const openEntry = () => {
    const vals = {
      title: book.title || "",
      author: a.author || "",
      publisher: a.publisher || "",
      isbn: a.isbn || "",
      format: a.format || "",
      edition: a.edition || "",
      series: a.series || "",
      publish_year: a.publish_year ?? "",
      image_url: book.image_url,
      tags: book.tags || [],
      notes: book.notes || "",
    };
    entryInit.current = vals;
    setEntry(vals);
  };

  const saveEntry = async () => {
    if (busy) return;
    if (!entry.title.trim()) return alert("A book needs a title.");
    setBusy(true);
    try {
      await api.updateBook(book.id, {
        title: entry.title.trim(),
        author: entry.author.trim() || null,
        publisher: entry.publisher.trim() || null,
        isbn: entry.isbn.trim() || null,
        format: entry.format || null,
        edition: entry.edition.trim() || null,
        series: entry.series.trim() || null,
        publish_year: entry.publish_year ? Number(entry.publish_year) : null,
        image_url: await api.localiseImage(entry.image_url),
        notes: entry.notes.trim() || null,
      });
      // Staged with the rest of the form, so Cancel discards a tag the
      // same way it discards a retyped title.
      await api.setItemTags(book.id, "books", entry.tags);
      onTagsChanged?.();
      setEntry(null);
      onReload();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      ref={rowRef}
      className={`game-row ${book.owned.length ? "row-owned" : ""} ${infoOpen || entry ? "open" : ""}`}
    >
      {book.image_url ? (
        <img
          className="game-cover"
          src={book.image_url}
          alt=""
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={() => setInfoOpen(!infoOpen)}
        />
      ) : (
        <span className="game-icon" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
          <Icon id="book" />
        </span>
      )}
      <span className="game-text" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
        <strong>{book.title}</strong>
        <small className="game-meta">
          {a.author && <span>{a.author}</span>}
          {a.format && <span className="plat-badge">{a.format}</span>}
          {a.publish_year && <span>{a.publish_year}</span>}
        </small>
        {book.owned.length > 0 && (
          <span className="copy-chips">
            {book.owned.map((o) => (
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
          onClick={() => (entry ? setEntry(null) : openEntry())}
          title="Edit entry"
        >
          <Icon id="pencil" />
        </button>
        <button className="ghost icon danger" onClick={del} title="Delete entry">
          <Icon id="trash" />
        </button>
      </span>

      {entry && (
        <span className="entry-edit">
          <span className="game-info-line">Edition details</span>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Title"
              value={entry.title}
              onChange={(e) => setEntry({ ...entry, title: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Author"
              value={entry.author}
              onChange={(e) => setEntry({ ...entry, author: e.target.value })}
            />
          </div>
          <div className="form-row">
            <select
              value={entry.format}
              onChange={(e) => setEntry({ ...entry, format: e.target.value })}
            >
              <option value="">Format…</option>
              {(FORMATS.includes(entry.format) || !entry.format
                ? FORMATS
                : [entry.format, ...FORMATS]
              ).map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Year"
              inputMode="numeric"
              value={entry.publish_year}
              onChange={(e) => setEntry({ ...entry, publish_year: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Edition (First, Folio…)"
              value={entry.edition}
              onChange={(e) => setEntry({ ...entry, edition: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Publisher"
              value={entry.publisher}
              onChange={(e) => setEntry({ ...entry, publisher: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "170px" }}
              placeholder="ISBN"
              value={entry.isbn}
              onChange={(e) => setEntry({ ...entry, isbn: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Series (optional)"
              value={entry.series}
              onChange={(e) => setEntry({ ...entry, series: e.target.value })}
            />
          </div>
          <div className="form-row">
            <TagEditor
              scope="books"
              id={book.id}
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
              label="Cover photo"
              onChange={(url) => setEntry({ ...entry, image_url: url })}
            />
            <button
              className="primary icon"
              onClick={saveEntry}
              disabled={busy}
              title="Save"
              style={{ marginLeft: "auto" }}
            >
              <Icon id="check" />
            </button>
            <button className="ghost icon" onClick={() => setEntry(null)} title="Cancel">
              <Icon id="x" />
            </button>
          </div>
        </span>
      )}

      {infoOpen && (
        <span className="entry-edit game-info">
          <div className="expand-card">
            {book.image_url && (
              <img className="expand-cover" src={book.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{book.title}</span>
              <span className="expand-sub">
                {[a.author, a.series].filter(Boolean).join(" · ") || "Unknown author"}
              </span>
              <span className="game-info-line">
                {[
                  a.format,
                  a.edition,
                  a.publish_year,
                  a.publisher,
                  a.page_count && `${a.page_count} pages`,
                  a.isbn && `ISBN ${a.isbn}`,
                ]
                  .filter(Boolean)
                  .join("  ·  ")}
              </span>
            </div>
            {/* the author, not the format: paperback vs hardcover is an
                edition, not a different medium, and sellers list both ways */}
            <EbayLink title={book.title} terms={[a.author]} />
          </div>
          <TagChips tags={book.tags} />
          {/* your own words about the thing, not about one copy */}
          {book.notes && <p className="game-summary">{book.notes}</p>}
          {a.blurb && <p className="game-summary">{a.blurb}</p>}
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
