import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { Icon } from "../components/Icons.jsx";
import ImagePicker from "../components/ImagePicker.jsx";

const FORMATS = ["Hardcover", "Paperback", "Trade Paperback", "Mass Market", "Leather", "Audiobook"];
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
  own: true,
  completeness: "With jacket",
  condition: "Very Good",
};

export default function BooksPage() {
  const [books, setBooks] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({ authors: [], formats: [] });
  const [search, setSearch] = useState("");
  const [authorFilter, setAuthorFilter] = useState("");
  const [formatFilter, setFormatFilter] = useState("");
  const [sort, setSort] = useState("title");
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
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, authorFilter, formatFilter, sort]);

  const lookup = async (params) => {
    setSearching(true);
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

  const textSearch = () => {
    const q = [form.title.trim(), form.author.trim()].filter(Boolean).join(" ");
    if (q.length < 2) return;
    lookup({ q });
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
    }));
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
      if (wantMode) navigate("/wanted");
      else load();
    } catch (err) {
      alert(err.message);
    }
  };

  const patchBook = (id, status) =>
    setBooks((bs) =>
      bs.map((b) => (b.id === id ? { ...b, owned: status.owned, wanted: status.wanted } : b))
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search title or author…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button
          className={showForm ? "ghost icon" : "primary"}
          onClick={() => setShowForm(!showForm)}
          title={showForm ? "Close" : "Add a book"}
        >
          <Icon id={showForm ? "x" : "plus"} />
          {!showForm && "Add"}
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
        <select
          className="chip-select"
          title="Sort"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          style={{ marginLeft: "auto" }}
        >
          <option value="title">A–Z</option>
          <option value="author">By author</option>
          <option value="year">By year</option>
          <option value="added">Last added</option>
        </select>
      </div>

      {showForm && (
        <form className="add-form" onSubmit={submit}>
          <h2>Add a book</h2>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
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
          <div className="form-row">
            <ImagePicker
              value={form.image_url}
              label="Cover photo"
              onChange={(url) => setForm({ ...form, image_url: url })}
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
      )}

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

      <div className="game-list">
        {books.map((b) => (
          <BookRow key={b.id} book={b} onChange={patchBook} onReload={load} />
        ))}
      </div>
    </div>
  );
}

function BookRow({ book, onChange, onReload }) {
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
  const openEntry = () =>
    setEntry({
      title: book.title || "",
      author: a.author || "",
      publisher: a.publisher || "",
      isbn: a.isbn || "",
      format: a.format || "",
      edition: a.edition || "",
      series: a.series || "",
      publish_year: a.publish_year ?? "",
      image_url: book.image_url,
    });

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
      });
      setEntry(null);
      onReload();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`game-row ${book.owned.length ? "row-owned" : ""}`}>
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
