import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { Icon } from "../components/Icons.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { TagChips, TagEditor, TagFilter } from "../components/Tags.jsx";
import { DEFAULT_VINYL_GRADE, VINYL_GRADES } from "../vocab.js";
import ViewToggle, { useTileView } from "../components/ViewToggle.jsx";
import { useListPref } from "../settings.jsx";

// "Vinyl box set", not "Box set": in a records collection a box set is almost
// always wax, and saying so is what keeps a price check off the CD edition.
const FORMATS = [
  '12" Vinyl', '2x12" Vinyl', '10" Vinyl', '7" Vinyl',
  "Vinyl box set", "CD", "Cassette",
];
const SPEEDS = ["33⅓", "45", "78"];

const EMPTY_FORM = {
  title: "",
  artist: "",
  label: "",
  catalog_number: "",
  format: '12" Vinyl',
  genre: "",
  speed: "33⅓",
  pressing: "",
  release_year: "",
  country: "",
  barcode: "",
  track_count: "",
  tracklist: null,
  image_url: null,
  tags: [],
  notes: "",
  own: true,
  condition: DEFAULT_VINYL_GRADE,
  sleeve_condition: DEFAULT_VINYL_GRADE,
};

// a select whose fixed options may not cover what a lookup returned
const withValue = (options, value) =>
  value && !options.includes(value) ? [value, ...options] : options;

// records are graded media-first, sleeve-second, written "VG+/VG"
const gradePair = (o) =>
  [o.condition, o.sleeve_condition].every((x) => !x)
    ? ""
    : `${o.condition || "?"}/${o.sleeve_condition || "?"}`;

// Shared wording, so every collection asks the same question the same way.
// Returns false only if the person says no.
async function confirmDuplicate(scope, title) {
  let matches = [];
  try {
    ({ matches } = await api.duplicates(scope, title));
  } catch {
    return true; // the check failing must never block an add
  }
  if (!matches.length) return true;
  const m = matches[0];
  const copies = m.copies === 1 ? "1 copy" : `${m.copies} copies`;
  return confirm(
    `${m.title} is already in this collection` +
      (m.detail ? ` — ${m.detail}` : "") +
      `, with ${copies}.

Add another?`
  );
}

export default function RecordsPage() {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({ artists: [], labels: [], formats: [], genres: [] });
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("records");
  const [artistFilter, setArtistFilter] = useListPref("records", "artistFilter", "");
  const [labelFilter, setLabelFilter] = useListPref("records", "labelFilter", "");
  const [formatFilter, setFormatFilter] = useListPref("records", "formatFilter", "");
  const [genreFilter, setGenreFilter] = useListPref("records", "genreFilter", "");
  const [tagFilter, setTagFilter] = useListPref("records", "tagFilter", "");
  // bumped whenever tags change, so the filter re-reads its counts
  const [tagsChanged, setTagsChanged] = useState(0);
  const [sort, setSort] = useListPref("records", "sort", "artist");
  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState("search"); // search -> details
  const [form, setForm] = useState(EMPTY_FORM);
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    const params = { sort };
    if (search) params.search = search;
    if (artistFilter) params.artist = artistFilter;
    if (labelFilter) params.label = labelFilter;
    if (formatFilter) params.format = formatFilter;
    if (genreFilter) params.genre = genreFilter;
    if (tagFilter) params.tag = tagFilter;
    api
      .records(params)
      .then((d) => {
        setRecords(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    api.recordFacets().then((f) => {
      setFacets(f);
      const gone = (list, v) => v && !list.some((x) => x.value === v);
      if (gone(f.artists, artistFilter)) setArtistFilter("");
      if (gone(f.labels, labelFilter)) setLabelFilter("");
      if (gone(f.formats, formatFilter)) setFormatFilter("");
      if (gone(f.genres || [], genreFilter)) setGenreFilter("");
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, artistFilter, labelFilter, formatFilter, genreFilter, tagFilter, sort, tagsChanged]);

  const lookup = async (params) => {
    setSearching(true);
    setResults(null); // clear the old hits so the status stands alone
    try {
      setResults(await api.musicBrainzSearch(params));
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  // the barcode on the sleeve identifies the exact pressing, which is the
  // whole game with vinyl — a repress and an original share everything else
  // keep the scanned digits on the form regardless of what the lookup returns —
  // it's the one fact about the pressing you know for certain
  const onBarcode = (code) => {
    setForm((f) => ({ ...f, barcode: code.replace(/\D/g, "") }));
    lookup({ barcode: code });
  };

  // title and artist go over as separate fields — MusicBrainz can scope the
  // query to the artist, which one blob of free text can't
  const textSearch = () => {
    const params = {};
    if (form.title.trim()) params.q = form.title.trim();
    if (form.artist.trim()) params.artist = form.artist.trim();
    if (!params.q && !params.artist) return;
    lookup(params);
  };

  const pickResult = (r) => {
    setForm((f) => ({
      ...f,
      title: r.title || f.title,
      artist: r.artist || "",
      label: r.label || "",
      catalog_number: r.catalog_number || "",
      format: r.format || f.format,
      genre: r.genre || "",
      // 7" singles spin at 45; everything else is an LP until told otherwise
      speed: r.speed || (/7"/.test(r.format || "") ? "45" : f.speed),
      // "Limited Edition, Reissue, Kith" — what separates this copy from the
      // ordinary pressing, and only Discogs tends to record it
      pressing: r.pressing || f.pressing,
      release_year: r.release_year || "",
      country: r.country || "",
      barcode: r.barcode || f.barcode,
      track_count: r.track_count || "",
      image_url: r.image_url || null,
      tracklist: null,
    }));
    setResults(null);
    setStep("details");
    // Only Discogs knows the running order, and only per pressing. A second
    // request, so the form opens now and fills itself in if one arrives.
    if (r.discogs_id) {
      api
        .recordTracklist(r.discogs_id)
        .then(({ tracklist }) => tracklist && setForm((f) => ({ ...f, tracklist })))
        .catch(() => {}); // MusicBrainz-only pressings simply have none
    }
  };

  const openForm = () => {
    setForm(EMPTY_FORM);
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
      // Ask before making a second one. Two identical rows take a moment
      // to create and a while to notice.
      if (!(await confirmDuplicate("records", form.title))) return;

      const created = await api.addRecord({
        title: form.title,
        artist: form.artist.trim() || null,
        label: form.label.trim() || null,
        catalog_number: form.catalog_number.trim() || null,
        format: form.format || null,
        genre: form.genre.trim() || null,
        speed: form.speed || null,
        pressing: form.pressing.trim() || null,
        release_year: form.release_year ? Number(form.release_year) : null,
        country: form.country.trim() || null,
        barcode: form.barcode.trim() || null,
        track_count: form.track_count ? Number(form.track_count) : null,
        tracklist: form.tracklist || null,
        // a sleeve photo from a shop listing outlives the listing this way
        image_url: await api.localiseImage(form.image_url),
        notes: form.notes.trim() || null,
      });
      // after the create, because a tag needs something to hang on
      if (form.tags.length) {
        await api.setItemTags(created.id, "records", form.tags);
        setTagsChanged((n) => n + 1);
      }
      if (form.own) {
        await api.addOwned(created.id, {
          condition: form.condition,
          sleeve_condition: form.sleeve_condition,
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

  const patchRecord = (id, status) =>
    setRecords((rs) =>
      rs.map((r) =>
        r.id === id
          ? { ...r, owned: status.owned, wanted: status.wanted, tags: status.tags ?? r.tags }
          : r
      )
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search album, artist or cat#…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button className="primary" onClick={openForm} title="Add a record">
          <Icon id="plus" />
          Add
        </button>
      </div>

      {/* one list, shared by the genre box on the add form and the edit
          form — typing beats picking, but not knowing beats both */}
      <datalist id="record-genres">
        {(facets.genres || []).map((g) => (
          <option key={g.value} value={g.value} />
        ))}
      </datalist>
      <div className="chip-row">
        {facets.formats.length > 0 && (
          <select
            className="chip-select"
            value={formatFilter}
            onChange={(e) => setFormatFilter(e.target.value)}
          >
            <option value="">All formats</option>
            {facets.formats.map((f) => (
              <option key={f.value} value={f.value}>
                {f.value} ({f.count})
              </option>
            ))}
          </select>
        )}
        {facets.artists.length > 0 && (
          <select
            className="chip-select"
            value={artistFilter}
            onChange={(e) => setArtistFilter(e.target.value)}
          >
            <option value="">All artists</option>
            {facets.artists.map((a) => (
              <option key={a.value} value={a.value}>
                {a.value} ({a.count})
              </option>
            ))}
          </select>
        )}
        {facets.genres?.length > 0 && (
          <select
            className="chip-select"
            value={genreFilter}
            onChange={(e) => setGenreFilter(e.target.value)}
          >
            <option value="">All genres</option>
            {facets.genres.map((g) => (
              <option key={g.value} value={g.value}>
                {g.value} ({g.count})
              </option>
            ))}
          </select>
        )}
        {facets.labels.length > 0 && (
          <select
            className="chip-select"
            value={labelFilter}
            onChange={(e) => setLabelFilter(e.target.value)}
          >
            <option value="">All labels</option>
            {facets.labels.map((l) => (
              <option key={l.value} value={l.value}>
                {l.value} ({l.count})
              </option>
            ))}
          </select>
        )}
        <TagFilter
          scope="records"
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
          <option value="artist">By artist</option>
          <option value="title">A–Z</option>
          <option value="label">By label</option>
          <option value="year">By year</option>
          <option value="added">Last added</option>
          <option value="oldest">First added</option>
        </select>
        <ViewToggle module="records" />
      </div>

      <AddSheet open={showForm && step === "search"} title="Find a record" onClose={closeForm}>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Album title"
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
              placeholder="Artist"
              value={form.artist}
              onChange={(e) => setForm({ ...form, artist: e.target.value })}
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
                {results.some((r) => r.source === "barcode")
                  ? "Not in the music databases — matched the barcode to a shop listing"
                  : `${
                      results.some((r) => r.source === "discogs")
                        ? "Discogs"
                        : "MusicBrainz"
                    } · ${results.length} match${results.length === 1 ? "" : "es"}`}
              </span>
              {results.length === 0 && (
                <p className="empty" style={{ padding: "var(--s-3)" }}>
                  Nothing found — fill the details in by hand below.
                </p>
              )}
              <div className="grid pick-grid">
                {results.map((r, i) => (
                  <div
                    key={r.mbid || i}
                    className={`tile pick square ${r.source === "barcode" ? "sel" : ""}`}
                    onClick={() => pickResult(r)}
                    title={
                      r.source === "barcode"
                        ? "The listing your barcode matched — fewest details, but the right pressing"
                        : "Use this pressing"
                    }
                  >
                    {r.image_url ? (
                      <img src={r.image_url} alt={r.title} loading="lazy" />
                    ) : (
                      <div className="placeholder" data-label="no cover" />
                    )}
                    <div className="tile-info">
                      <strong>{r.title}</strong>
                      <small>{r.artist || "—"}</small>
                      <small>
                        {r.source === "barcode"
                          ? "matches your barcode"
                          : [r.format, r.release_year, r.country]
                              .filter(Boolean)
                              .join(" · ")}
                      </small>
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
        title="Add a record"
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
              placeholder="Artist"
              value={form.artist}
              onChange={(e) => setForm({ ...form, artist: e.target.value })}
            />
          </div>
          <div className="form-row">
            <select
              value={form.format}
              onChange={(e) => setForm({ ...form, format: e.target.value })}
            >
              {withValue(FORMATS, form.format).map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
            <select
              title="Speed (RPM)"
              value={form.speed}
              onChange={(e) => setForm({ ...form, speed: e.target.value })}
            >
              {withValue(SPEEDS, form.speed).map((s) => (
                <option key={s} value={s}>
                  {s} RPM
                </option>
              ))}
            </select>
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Year"
              inputMode="numeric"
              value={form.release_year}
              onChange={(e) => setForm({ ...form, release_year: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Label (Blue Note, 4AD…)"
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "170px" }}
              placeholder="Catalogue no."
              value={form.catalog_number}
              onChange={(e) => setForm({ ...form, catalog_number: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Pressing (180g, clear vinyl, reissue…)"
              value={form.pressing}
              onChange={(e) => setForm({ ...form, pressing: e.target.value })}
            />
            <input
              type="text"
              list="record-genres"
              style={{ maxWidth: "140px" }}
              placeholder="Genre"
              value={form.genre}
              onChange={(e) => setForm({ ...form, genre: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "90px" }}
              placeholder="Country"
              value={form.country}
              onChange={(e) => setForm({ ...form, country: e.target.value })}
            />
          </div>
          <div className="form-row">
            <ImagePicker
              value={form.image_url}
              label="Sleeve photo"
              square
              onChange={(url) => setForm({ ...form, image_url: url })}
            />
          </div>
          {/* last of the fields, because a tag is the one thing here you
              think of after everything else is filled in */}
          <div className="form-row">
            <TagEditor
              scope="records"
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
              title="Media grade — the disc itself"
              value={form.condition}
              onChange={(e) => setForm({ ...form, condition: e.target.value })}
            >
              {VINYL_GRADES.map(([g, label]) => (
                <option key={g} value={g}>
                  Media: {label}
                </option>
              ))}
            </select>
            <select
              disabled={!form.own}
              title="Sleeve grade — the cover"
              value={form.sleeve_condition}
              onChange={(e) => setForm({ ...form, sleeve_condition: e.target.value })}
            >
              {VINYL_GRADES.map(([g, label]) => (
                <option key={g} value={g}>
                  Sleeve: {label}
                </option>
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
      {!error && loaded && records.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="vinyl" /></span>
          <strong>No records yet</strong>
          <p>Scan the barcode on the sleeve, or search by artist and album.</p>
        </div>
      )}

      <div className={`game-list ${tiles ? "as-tiles" : ""}`}>
        {records.map((r) => (
          <RecordRow
            key={r.id}
            record={r}
            onChange={patchRecord}
            onReload={load}
            onTagsChanged={() => setTagsChanged((n) => n + 1)}
          />
        ))}
      </div>
    </div>
  );
}

function RecordRow({ record, onChange, onReload, onTagsChanged }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editVals, setEditVals] = useState({
    condition: DEFAULT_VINYL_GRADE,
    sleeve_condition: DEFAULT_VINYL_GRADE,
  });
  const [infoOpen, setInfoOpen] = useState(false);
  const a = record.attrs;

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      onChange(record.id, await fn());
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeCopy = (o) => {
    if (!confirm(`Remove this copy of ${record.title} (${gradePair(o) || "copy"})?`)) return;
    run(() => api.removeOwned(record.id, o.id));
  };
  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      condition: o.condition || DEFAULT_VINYL_GRADE,
      sleeve_condition: o.sleeve_condition || DEFAULT_VINYL_GRADE,
    });
  };
  const saveEdit = () =>
    run(async () => {
      const s = await api.updateOwned(record.id, editing, editVals);
      setEditing(null);
      return s;
    });

  const del = async () => {
    if (!confirm(`Delete "${record.title}" and its copies?`)) return;
    await api.deleteRecord(record.id);
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
    () => keepOpen(entry, entryInit.current, entry !== null, record.title),
  );
  const openEntry = () => {
    const vals = {
      title: record.title || "",
      artist: a.artist || "",
      label: a.label || "",
      catalog_number: a.catalog_number || "",
      format: a.format || "",
      genre: a.genre || "",
      speed: a.speed || "",
      pressing: a.pressing || "",
      release_year: a.release_year ?? "",
      country: a.country || "",
      image_url: record.image_url,
      tags: record.tags || [],
      notes: record.notes || "",
    };
    entryInit.current = vals;
    setEntry(vals);
  };

  const saveEntry = async () => {
    if (busy) return;
    if (!entry.title.trim()) return alert("A record needs a title.");
    setBusy(true);
    try {
      await api.updateRecord(record.id, {
        title: entry.title.trim(),
        artist: entry.artist.trim() || null,
        label: entry.label.trim() || null,
        catalog_number: entry.catalog_number.trim() || null,
        format: entry.format || null,
        genre: entry.genre.trim() || null,
        speed: entry.speed || null,
        pressing: entry.pressing.trim() || null,
        country: entry.country.trim() || null,
        // blank clears the year rather than storing 0
        release_year: entry.release_year ? Number(entry.release_year) : null,
        image_url: await api.localiseImage(entry.image_url),
        notes: entry.notes.trim() || null,
      });
      // Staged with the rest of the form rather than saved on the spot, so
      // Cancel discards a tag the same way it discards a retyped title.
      await api.setItemTags(record.id, "records", entry.tags);
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
      className={`game-row ${record.owned.length ? "row-owned" : ""} ${infoOpen || entry ? "open" : ""}`}
    >
      {record.image_url ? (
        <img
          className="game-cover"
          src={record.image_url}
          alt=""
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={() => setInfoOpen(!infoOpen)}
        />
      ) : (
        <span className="game-icon" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
          <Icon id="vinyl" />
        </span>
      )}
      <span className="game-text" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
        <strong>{record.title}</strong>
        <small className="game-meta">
          {a.artist && <span>{a.artist}</span>}
          {a.format && <span className="plat-badge">{a.format}</span>}
          {a.release_year && <span>{a.release_year}</span>}
        </small>
        {record.owned.length > 0 && (
          <span className="copy-chips">
            {record.owned.map((o) => (
              <span
                key={o.id}
                className="chip copy"
                onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
                title="Media / sleeve grade — click to edit"
              >
                <Icon id="pencil" />
                {gradePair(o) || "set grades…"}
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
          <span className="game-info-line">Pressing details</span>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Album title"
              value={entry.title}
              onChange={(e) => setEntry({ ...entry, title: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Artist"
              value={entry.artist}
              onChange={(e) => setEntry({ ...entry, artist: e.target.value })}
            />
          </div>
          <div className="form-row">
            <select
              value={entry.format}
              onChange={(e) => setEntry({ ...entry, format: e.target.value })}
            >
              <option value="">Format…</option>
              {withValue(FORMATS, entry.format).map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
            <select
              title="Speed (RPM)"
              value={entry.speed}
              onChange={(e) => setEntry({ ...entry, speed: e.target.value })}
            >
              <option value="">Speed…</option>
              {withValue(SPEEDS, entry.speed).map((s) => (
                <option key={s} value={s}>
                  {s} RPM
                </option>
              ))}
            </select>
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Year"
              inputMode="numeric"
              value={entry.release_year}
              onChange={(e) => setEntry({ ...entry, release_year: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Label"
              value={entry.label}
              onChange={(e) => setEntry({ ...entry, label: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "170px" }}
              placeholder="Catalogue no."
              value={entry.catalog_number}
              onChange={(e) => setEntry({ ...entry, catalog_number: e.target.value })}
            />
            <input
              type="text"
              list="record-genres"
              style={{ maxWidth: "140px" }}
              placeholder="Genre"
              value={entry.genre}
              onChange={(e) => setEntry({ ...entry, genre: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "90px" }}
              placeholder="Country"
              value={entry.country}
              onChange={(e) => setEntry({ ...entry, country: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Pressing (180g, clear vinyl, reissue…)"
              value={entry.pressing}
              onChange={(e) => setEntry({ ...entry, pressing: e.target.value })}
            />
          </div>
          <div className="form-row">
            <TagEditor
              scope="records"
              id={record.id}
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
              label="Sleeve photo"
              square
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
            {record.image_url && (
              <img className="expand-cover square" src={record.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{record.title}</span>
              <span className="expand-sub">{a.artist || "Unknown artist"}</span>
              <span className="game-info-line">
                {[
                  a.format,
                  a.genre,
                  a.speed && `${a.speed} RPM`,
                  a.release_year,
                  a.country,
                  a.label,
                  a.catalog_number,
                  a.track_count && `${a.track_count} tracks`,
                ]
                  .filter(Boolean)
                  .join("  ·  ")}
              </span>
              {a.pressing && <span className="game-info-line">{a.pressing}</span>}
            </div>
            {/* an artist and album alone pull up the CD, the cassette and the
                download — the pressing format is what makes it a record */}
            <EbayLink title={record.title} terms={[a.artist, a.format]} />
          </div>
          {/* Positions are kept as Discogs lists them, because on a record
              "B2" is where the track physically is, not just its number. */}
          {/* Shown, not edited. Opening the description is reading; changing
              what a record says is what the pencil is for, and a box that
              writes the moment you type in it does not belong on a panel with
              nothing to confirm it. */}
          <TagChips tags={record.tags} />
          {/* your own words about the thing, not about one copy */}
          {record.notes && <p className="game-summary">{record.notes}</p>}
          {a.tracklist && (
            <ol className="tracklist">
              {a.tracklist.split("\n").map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ol>
          )}
        </span>
      )}

      {editing !== null && (
        <span className="copy-edit">
          <select
            title="Media grade"
            value={editVals.condition}
            onChange={(e) => setEditVals({ ...editVals, condition: e.target.value })}
          >
            {VINYL_GRADES.map(([g, label]) => (
              <option key={g} value={g}>
                Media: {label}
              </option>
            ))}
          </select>
          <select
            title="Sleeve grade"
            value={editVals.sleeve_condition}
            onChange={(e) => setEditVals({ ...editVals, sleeve_condition: e.target.value })}
          >
            {VINYL_GRADES.map(([g, label]) => (
              <option key={g} value={g}>
                Sleeve: {label}
              </option>
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
