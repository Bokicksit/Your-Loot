import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import ArtOptions from "../components/ArtOptions.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { Icon } from "../components/Icons.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { LEGO_COMPLETENESS, LEGO_CONDITION, labelFor, shortFor, withUnknown } from "../vocab.js";
import ViewToggle, { useTileView } from "../components/ViewToggle.jsx";

const EMPTY_FORM = {
  title: "",
  set_number: "",
  theme: "",
  subtheme: "",
  release_year: "",
  piece_count: "",
  minifig_count: "",
  barcode: "",
  image_url: null,
  own: true,
  completeness: "complete+box",
  condition: "used",
};

const copyLabel = (o) =>
  [
    o.completeness && shortFor(LEGO_COMPLETENESS, o.completeness),
    o.condition && labelFor(LEGO_CONDITION, o.condition),
  ]
    .filter(Boolean)
    .join(" · ");

export default function LegoPage() {
  const [sets, setSets] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({ themes: [], years: [] });
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("lego");
  const [themeFilter, setThemeFilter] = useState("");
  const [sort, setSort] = useState("title");
  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState("search"); // search -> details
  const [form, setForm] = useState(EMPTY_FORM);
  const [results, setResults] = useState(null);
  const [art, setArt] = useState([]); // retailer photos of the actual box
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    const params = { sort };
    if (search) params.search = search;
    if (themeFilter) params.theme = themeFilter;
    api
      .lego(params)
      .then((d) => {
        setSets(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    api.legoFacets().then((f) => {
      setFacets(f);
      if (themeFilter && !f.themes.some((t) => t.value === themeFilter)) setThemeFilter("");
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, themeFilter, sort]);

  const lookup = async (params) => {
    setSearching(true);
    setResults(null); // clear the old hits so the status stands alone
    try {
      setResults(await api.rebrickableSearch(params));
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  // Rebrickable doesn't index barcodes, but the shops do — and their listings
  // carry photographs of the actual box, which Rebrickable's set image isn't:
  // that's the built model on white. So the scan goes the long way round, the
  // same as games and movies, and the set number usually falls out of the
  // product title into a real Rebrickable search.
  const onBarcode = async (code) => {
    setForm((f) => ({ ...f, barcode: code }));
    let res;
    try {
      res = await api.barcodeLookup(code);
    } catch (e) {
      alert(e.message);
      return;
    }
    if (!res.found) {
      alert("No product match for that barcode — search by set name or number.");
      return;
    }
    const raw = res.titles[0].title;
    const boxArt = (res.titles[0].images || []).map((url) => ({ url, kind: "box" }));
    setArt(boxArt);
    // "LEGO Star Wars Millennium Falcon 75192" — a LEGO set number is 4-7
    // digits, and the year is the only other number that turns up in these
    // titles, so anything reading like one is left alone
    const nums = [...raw.matchAll(/\b(\d{4,7})\b/g)].map((m) => m[1]);
    const setNo = nums.find((n) => !(n.length === 4 && Number(n) >= 1900 && Number(n) <= 2099));
    setForm((f) => ({
      ...f,
      title: f.title || raw,
      image_url: boxArt[0]?.url || f.image_url,
      ...(setNo ? { set_number: setNo } : {}),
    }));
    if (setNo) lookup({ set_number: setNo });
  };

  const textSearch = () => {
    if (form.set_number.trim()) return lookup({ set_number: form.set_number.trim() });
    if (form.title.trim().length < 2) return;
    lookup({ q: form.title.trim() });
  };

  const pickResult = (r) => {
    setForm((f) => ({
      ...f,
      title: r.title || f.title,
      set_number: r.set_number || "",
      theme: r.theme || "",
      release_year: r.release_year || "",
      piece_count: r.piece_count || "",
      image_url: r.image_url || null,
    }));
    setResults(null);
    setStep("details");
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
      const created = await api.addLego({
        title: form.title,
        set_number: form.set_number.trim() || null,
        theme: form.theme.trim() || null,
        subtheme: form.subtheme.trim() || null,
        release_year: form.release_year ? Number(form.release_year) : null,
        piece_count: form.piece_count ? Number(form.piece_count) : null,
        minifig_count: form.minifig_count ? Number(form.minifig_count) : null,
        barcode: form.barcode.trim() || null,
        image_url: form.image_url,
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

  const patchSet = (id, status) =>
    setSets((ss) =>
      ss.map((s) => (s.id === id ? { ...s, owned: status.owned, wanted: status.wanted } : s))
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search set, number or theme…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button className="primary" onClick={openForm} title="Add a set">
          <Icon id="plus" />
          Add
        </button>
      </div>

      <div className="chip-row">
        {facets.themes.length > 0 && (
          <select
            className="chip-select"
            value={themeFilter}
            onChange={(e) => setThemeFilter(e.target.value)}
          >
            <option value="">All themes</option>
            {facets.themes.map((t) => (
              <option key={t.value} value={t.value}>
                {t.value} ({t.count})
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
          <option value="theme">By theme</option>
          <option value="number">By set number</option>
          <option value="year">By year</option>
          <option value="pieces">By piece count</option>
          <option value="added">Last added</option>
          <option value="oldest">First added</option>
        </select>
        <ViewToggle module="lego" />
      </div>

      <AddSheet open={showForm && step === "search"} title="Find a set" onClose={closeForm}>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Set name"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), textSearch())}
            />
            <BarcodeScan onCode={onBarcode} />
          </div>
          <div className="form-row">
            <input
              type="text"
              style={{ maxWidth: "170px" }}
              placeholder="Set number"
              value={form.set_number}
              onChange={(e) => setForm({ ...form, set_number: e.target.value })}
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
                Rebrickable · {results.length} match{results.length === 1 ? "" : "es"}
              </span>
              {results.length === 0 && (
                <p className="empty" style={{ padding: "var(--s-3)" }}>
                  Nothing found — fill the details in by hand below.
                </p>
              )}
              <div className="grid pick-grid">
                {results.map((r, i) => (
                  <div
                    key={r.set_number || i}
                    className="tile pick"
                    onClick={() => pickResult(r)}
                    title="Use this set"
                  >
                    {r.image_url ? (
                      <img src={r.image_url} alt={r.title} loading="lazy" />
                    ) : (
                      <div className="placeholder" data-label="no photo" />
                    )}
                    <div className="tile-info">
                      <strong>{r.title}</strong>
                      <small>{r.set_number}</small>
                      <small>
                        {[r.theme, r.release_year, r.piece_count && `${r.piece_count} pcs`]
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
        title="Add a set"
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
              placeholder="Set number"
              value={form.set_number}
              onChange={(e) => setForm({ ...form, set_number: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Theme (Star Wars, Modular…)"
              value={form.theme}
              onChange={(e) => setForm({ ...form, theme: e.target.value })}
            />
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
              placeholder="Subtheme (optional)"
              value={form.subtheme}
              onChange={(e) => setForm({ ...form, subtheme: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Pieces"
              inputMode="numeric"
              value={form.piece_count}
              onChange={(e) => setForm({ ...form, piece_count: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Minifigs"
              inputMode="numeric"
              value={form.minifig_count}
              onChange={(e) => setForm({ ...form, minifig_count: e.target.value })}
            />
          </div>
          {/* photos of the actual box from the scanned barcode, alongside
              Rebrickable's set image — which is the built model, not the box */}
          <ArtOptions
            options={art}
            value={form.image_url}
            onChange={(url) => setForm({ ...form, image_url: url })}
          />
          <div className="form-row">
            <ImagePicker
              value={form.image_url}
              label="Set photo"
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
              title="What you have"
              value={form.completeness}
              onChange={(e) => setForm({ ...form, completeness: e.target.value })}
            >
              {LEGO_COMPLETENESS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <select
              disabled={!form.own}
              title="Condition"
              value={form.condition}
              onChange={(e) => setForm({ ...form, condition: e.target.value })}
            >
              {LEGO_CONDITION.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
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
      {!error && loaded && sets.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="brick" /></span>
          <strong>No sets yet</strong>
          <p>Type the set number from the corner of the box, or search by name.</p>
        </div>
      )}

      <div className={`game-list ${tiles ? "as-tiles" : ""}`}>
        {sets.map((s) => (
          <LegoRow key={s.id} set={s} onChange={patchSet} onReload={load} />
        ))}
      </div>
    </div>
  );
}

function LegoRow({ set, onChange, onReload }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editVals, setEditVals] = useState({ completeness: "complete+box", condition: "used" });
  const [infoOpen, setInfoOpen] = useState(false);
  const a = set.attrs;

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      onChange(set.id, await fn());
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeCopy = (o) => {
    if (!confirm(`Remove this copy of ${set.title} (${copyLabel(o) || "copy"})?`)) return;
    run(() => api.removeOwned(set.id, o.id));
  };
  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      completeness: o.completeness || "complete+box",
      condition: o.condition || "used",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const s = await api.updateOwned(set.id, editing, editVals);
      setEditing(null);
      return s;
    });

  const del = async () => {
    if (!confirm(`Delete "${set.title}" and its copies?`)) return;
    await api.deleteLego(set.id);
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
    () => keepOpen(entry, entryInit.current, entry !== null, set.title),
  );
  const openEntry = () => {
    const vals = {
      title: set.title || "",
      set_number: a.set_number || "",
      theme: a.theme || "",
      subtheme: a.subtheme || "",
      release_year: a.release_year ?? "",
      piece_count: a.piece_count ?? "",
      minifig_count: a.minifig_count ?? "",
      image_url: set.image_url,
    };
    entryInit.current = vals;
    setEntry(vals);
  };

  const saveEntry = async () => {
    if (busy) return;
    if (!entry.title.trim()) return alert("A set needs a name.");
    setBusy(true);
    try {
      await api.updateLego(set.id, {
        title: entry.title.trim(),
        set_number: entry.set_number.trim() || null,
        theme: entry.theme.trim() || null,
        subtheme: entry.subtheme.trim() || null,
        release_year: entry.release_year ? Number(entry.release_year) : null,
        piece_count: entry.piece_count ? Number(entry.piece_count) : null,
        minifig_count: entry.minifig_count ? Number(entry.minifig_count) : null,
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
    <div ref={rowRef} className={`game-row ${set.owned.length ? "row-owned" : ""}`}>
      {set.image_url ? (
        <img
          className="game-cover"
          src={set.image_url}
          alt=""
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={() => setInfoOpen(!infoOpen)}
        />
      ) : (
        <span className="game-icon" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
          <Icon id="brick" />
        </span>
      )}
      <span className="game-text" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
        <strong>{set.title}</strong>
        <small className="game-meta">
          {a.set_number && <span className="plat-badge">{a.set_number}</span>}
          {a.theme && <span>{a.theme}</span>}
          {a.release_year && <span>{a.release_year}</span>}
        </small>
        {set.owned.length > 0 && (
          <span className="copy-chips">
            {set.owned.map((o) => (
              <span
                key={o.id}
                className="chip copy"
                onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
                title="Edit this copy"
              >
                <Icon id="pencil" />
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
          <span className="game-info-line">Set details</span>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Set name"
              value={entry.title}
              onChange={(e) => setEntry({ ...entry, title: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "170px" }}
              placeholder="Set number"
              value={entry.set_number}
              onChange={(e) => setEntry({ ...entry, set_number: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Theme"
              value={entry.theme}
              onChange={(e) => setEntry({ ...entry, theme: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Subtheme (optional)"
              value={entry.subtheme}
              onChange={(e) => setEntry({ ...entry, subtheme: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Year"
              inputMode="numeric"
              value={entry.release_year}
              onChange={(e) => setEntry({ ...entry, release_year: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Pieces"
              inputMode="numeric"
              value={entry.piece_count}
              onChange={(e) => setEntry({ ...entry, piece_count: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Minifigs"
              inputMode="numeric"
              value={entry.minifig_count}
              onChange={(e) => setEntry({ ...entry, minifig_count: e.target.value })}
            />
          </div>
          <div className="form-row">
            <ImagePicker
              value={entry.image_url}
              label="Set photo"
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
            {set.image_url && (
              <img className="expand-cover" src={set.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{set.title}</span>
              <span className="expand-sub">
                {[a.set_number, a.theme, a.subtheme].filter(Boolean).join(" · ") || "No set number"}
              </span>
              <span className="game-info-line">
                {[
                  a.release_year,
                  a.piece_count && `${a.piece_count} pieces`,
                  a.minifig_count && `${a.minifig_count} minifigs`,
                  a.barcode && `Barcode ${a.barcode}`,
                ]
                  .filter(Boolean)
                  .join("  ·  ")}
              </span>
            </div>
            {/* the set number is how LEGO is bought and sold, full stop */}
            <EbayLink title={set.title} terms={[a.set_number]} />
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
            {withUnknown(LEGO_COMPLETENESS, editVals.completeness).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <select
            title="Condition"
            value={editVals.condition}
            onChange={(e) => setEditVals({ ...editVals, condition: e.target.value })}
          >
            {withUnknown(LEGO_CONDITION, editVals.condition).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
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
