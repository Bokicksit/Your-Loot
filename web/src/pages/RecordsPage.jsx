import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import BarcodeScan from "../components/BarcodeScan.jsx";
import { Icon } from "../components/Icons.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { DEFAULT_VINYL_GRADE, VINYL_GRADES } from "../grades.js";

const FORMATS = ['12" Vinyl', '2x12" Vinyl', '10" Vinyl', '7" Vinyl', "Box set", "CD", "Cassette"];
const SPEEDS = ["33⅓", "45", "78"];

const EMPTY_FORM = {
  title: "",
  artist: "",
  label: "",
  catalog_number: "",
  format: '12" Vinyl',
  speed: "33⅓",
  pressing: "",
  release_year: "",
  country: "",
  barcode: "",
  track_count: "",
  image_url: null,
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

export default function RecordsPage() {
  const [records, setRecords] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({ artists: [], labels: [], formats: [] });
  const [search, setSearch] = useState("");
  const [artistFilter, setArtistFilter] = useState("");
  const [labelFilter, setLabelFilter] = useState("");
  const [formatFilter, setFormatFilter] = useState("");
  const [sort, setSort] = useState("artist");
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
    if (artistFilter) params.artist = artistFilter;
    if (labelFilter) params.label = labelFilter;
    if (formatFilter) params.format = formatFilter;
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
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, artistFilter, labelFilter, formatFilter, sort]);

  const lookup = async (params) => {
    setSearching(true);
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
  const onBarcode = (code) => lookup({ barcode: code });

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
      // 7" singles spin at 45; everything else is an LP until told otherwise
      speed: /7"/.test(r.format || "") ? "45" : f.speed,
      release_year: r.release_year || "",
      country: r.country || "",
      barcode: r.barcode || f.barcode,
      track_count: r.track_count || "",
      image_url: r.image_url || null,
    }));
    setResults(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      const created = await api.addRecord({
        title: form.title,
        artist: form.artist.trim() || null,
        label: form.label.trim() || null,
        catalog_number: form.catalog_number.trim() || null,
        format: form.format || null,
        speed: form.speed || null,
        pressing: form.pressing.trim() || null,
        release_year: form.release_year ? Number(form.release_year) : null,
        country: form.country.trim() || null,
        barcode: form.barcode.trim() || null,
        track_count: form.track_count ? Number(form.track_count) : null,
        image_url: form.image_url,
      });
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
      rs.map((r) => (r.id === id ? { ...r, owned: status.owned, wanted: status.wanted } : r))
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
        <button
          className={showForm ? "ghost icon" : "primary"}
          onClick={() => setShowForm(!showForm)}
          title={showForm ? "Close" : "Add a record"}
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
        <select
          className="chip-select"
          title="Sort"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          style={{ marginLeft: "auto" }}
        >
          <option value="artist">By artist</option>
          <option value="title">A–Z</option>
          <option value="year">By year</option>
          <option value="added">Last added</option>
        </select>
      </div>

      {showForm && (
        <form className="add-form" onSubmit={submit}>
          <h2>Add a record</h2>
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

          {results && (
            <>
              <span className="game-info-line">
                MusicBrainz · {results.length} match{results.length === 1 ? "" : "es"}
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
                    className="tile pick"
                    onClick={() => pickResult(r)}
                    title="Use this pressing"
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
                        {[r.format, r.release_year, r.country].filter(Boolean).join(" · ")}
                      </small>
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
      )}

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

      <div className="game-list">
        {records.map((r) => (
          <RecordRow key={r.id} record={r} onChange={patchRecord} onReload={load} />
        ))}
      </div>
    </div>
  );
}

function RecordRow({ record, onChange, onReload }) {
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

  return (
    <div className={`game-row ${record.owned.length ? "row-owned" : ""}`}>
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
      <button className="ghost icon danger" onClick={del} title="Delete entry">
        <Icon id="trash" />
      </button>

      {infoOpen && (
        <span className="entry-edit game-info">
          <div className="expand-card">
            {record.image_url && (
              <img className="expand-cover" src={record.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{record.title}</span>
              <span className="expand-sub">{a.artist || "Unknown artist"}</span>
              <span className="game-info-line">
                {[
                  a.format,
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
          </div>
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
