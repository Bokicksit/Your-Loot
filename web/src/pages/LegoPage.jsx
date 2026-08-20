import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import ArtOptions from "../components/ArtOptions.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import HelpTip from "../components/HelpTip.jsx";
import { Icon } from "../components/Icons.jsx";
import { TagChips, TagEditor, TagFilter } from "../components/Tags.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import {
  LEGO_COMPLETENESS,
  LEGO_CONDITION,
  LEGO_NEEDS_BOX,
  labelFor,
  shortFor,
  withUnknown,
} from "../vocab.js";
import ViewToggle, {
  useTileView,
  useTileCols,
  useInlineDensity,
  TileDensity,
} from "../components/ViewToggle.jsx";
import { useListPref, useSettings } from "../settings.jsx";

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
  tags: [],
  notes: "",
  own: true,
  completeness: "open",
  has_box: true,
  condition: "used",
};

const copyLabel = (o) =>
  [
    o.completeness && shortFor(LEGO_COMPLETENESS, o.completeness),
    o.has_box ? "+ box" : null,
    o.condition && labelFor(LEGO_CONDITION, o.condition),
  ]
    .filter(Boolean)
    .join(" · ");

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

export default function LegoPage() {
  const [sets, setSets] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({ themes: [], years: [] });
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("lego");
  const [tileCols] = useTileCols("lego");
  const inlineDensity = useInlineDensity();
  const [themeFilter, setThemeFilter] = useListPref("lego", "themeFilter", "");
  const [tagFilter, setTagFilter] = useListPref("lego", "tagFilter", "");
  // bumped whenever tags change, so the filter re-reads its counts
  const [tagsChanged, setTagsChanged] = useState(0);
  const [sort, setSort] = useListPref("lego", "sort", "title");
  // Shown while you fill the form in, not thrown at you on save.
  const [dupe, setDupe] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  // sort is not counted: it never hides anything, and a badge for the
  // order you always use would announce a problem that is not there
  const activeFilters = [themeFilter, tagFilter].filter(Boolean).length;
  // One write. Each useListPref setter rebuilds the whole prefs object
  // from its render-time copy, so several in a row undo each other.
  const { settings: allSettings, save: saveSettings } = useSettings();
  const clearFilters = () =>
    saveSettings({
      list_prefs: {
        ...(allSettings?.list_prefs || {}),
        lego: {
          ...(allSettings?.list_prefs?.lego || {}),
            themeFilter: "",
            tagFilter: "",
        },
      },
    });
  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState("search"); // search -> details
  const [form, setForm] = useState(EMPTY_FORM);
  const [results, setResults] = useState(null);
  const [art, setArt] = useState([]); // retailer photos of the actual box
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
    if (!showForm) return setDupe(null);
    const t = setTimeout(
      () => duplicateNotice("lego", form.title).then(setDupe),
      350
    );
    return () => clearTimeout(t);
  }, [showForm, form.title]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, themeFilter, sort, tagFilter, tagsChanged]);

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

  const CATALOG_ART = /rebrickable/i;
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
      set_number: r.set_number || "",
      theme: r.theme || "",
      release_year: r.release_year || "",
      piece_count: r.piece_count || "",
      image_url: r.image_url || null,
    }));
    findRetailArt(r.title, form.set_number);
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
        notes: form.notes.trim() || null,
      });
      // after the create, because a tag needs something to hang on
      if (form.tags.length) {
        await api.setItemTags(created.id, "lego", form.tags);
        setTagsChanged((n) => n + 1);
      }
      if (form.own) {
        await api.addOwned(created.id, {
          condition: form.condition,
          completeness: form.completeness,
          has_box: !!form.has_box,
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
      ss.map((s) => (s.id === id ? { ...s, owned: status.owned, wanted: status.wanted, tags: status.tags ?? set.tags } : s))
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
            placeholder="Search set, number or theme…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <span className="count">{total}</span>
        </label>
        <button className="primary" onClick={openForm} title="Add a set">
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
        <ViewToggle module="lego" />
        {tiles && inlineDensity && <TileDensity module="lego" />}
      </div>
      {filtersOpen && (
        <div className="filter-sheet">
          <label>
            <span>Theme</span>
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
          </label>
          <label>
            <span>Tag</span>
          <TagFilter
            scope="lego"
            value={tagFilter}
            onChange={setTagFilter}
            reloadKey={tagsChanged}
          />
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
            <option value="theme">By theme</option>
            <option value="number">By set number</option>
            <option value="year">By year</option>
            <option value="pieces">By piece count</option>
            <option value="added">Last added</option>
            <option value="oldest">First added</option>
          </select>
          </label>
          {activeFilters > 0 && (
            <button type="button" className="ghost" onClick={clearFilters}>
              Clear {activeFilters === 1 ? "filter" : "all filters"}
            </button>
          )}
        </div>
      )}
      {/* its own row, not a chip in the rail — inside a line that
          scrolls sideways it slid under the filter beside it */}
      {tiles && !inlineDensity && <TileDensity module="lego" />}

      <AddSheet
        open={showForm && step === "search"}
        title="Find a set"
        onClose={closeForm}
        help={
          <>
            The <b>set number</b> printed on the box is the exact way in —
            Rebrickable answers with that set alone. A name works too when
            the number's long gone, and the frame button scans the box's
            barcode. <b>Enter it by hand</b> files MOCs and anything else
            without a number.
          </>
        }
      >
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
        help={
          <>
            The catalogue fills in the set's own facts — pieces, year, theme.
            What it can't know is the box in your hands: <b>I own it</b> files
            your copy with its state (sealed, built, loose bricks…) and
            whether the box survived; <b>I want it</b> puts it on the wanted
            list instead. Everything stays editable later.
          </>
        }
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
          {dupe && <p className="dupe-note">{dupe}</p>}
          {/* last of the fields: a tag is what you think of once the rest
              is filled in */}
          <div className="form-row">
            <TagEditor
              scope="lego"
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
            <button
              type="button"
              className={`toggle ${form.has_box ? "on" : ""}`}
              disabled={!form.own || form.completeness === LEGO_NEEDS_BOX}
              title={
                form.completeness === LEGO_NEEDS_BOX
                  ? "A sealed set is in its box by definition"
                  : "Did you keep the box?"
              }
              onClick={() => setForm({ ...form, has_box: !form.has_box })}
            >
              {form.has_box ? "With box" : "No box"}
            </button>
            <select
              disabled={!form.own}
              title="What you have"
              value={form.completeness}
              onChange={(e) => {
                const completeness = e.target.value;
                // Sealed means in the box; letting the two disagree would
                // record a set that cannot exist.
                setForm((f) => ({
                  ...f,
                  completeness,
                  has_box: completeness === LEGO_NEEDS_BOX ? true : f.has_box,
                }));
              }}
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

      <div
        className={`game-list ${tiles ? `as-tiles cols-${tileCols}` : ""}`}
        style={tiles ? { "--tile-cols": tileCols } : undefined}
      >
        {sets.map((s) => (
          <LegoRow key={s.id} set={s} onChange={patchSet} onReload={load}
            onTagsChanged={() => setTagsChanged((n) => n + 1)} />
        ))}
      </div>
    </div>
  );
}

function LegoRow({ set, onChange, onReload , onTagsChanged}) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editVals, setEditVals] = useState({
    completeness: "open",
    has_box: true,
    condition: "used",
  });
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
      completeness: o.completeness || "open",
      has_box: o.has_box ?? true,
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
      tags: set.tags || [],
      notes: set.notes || "",
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
        notes: entry.notes.trim() || null,
      });
      // Staged with the rest of the form, so Cancel discards a tag the
      // same way it discards a retyped title.
      await api.setItemTags(set.id, "lego", entry.tags);
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
      className={`game-row ${set.owned.length ? "row-owned" : ""} ${infoOpen || entry ? "open" : ""}`}
    >
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
          <span className="game-info-line">
            Set details
            <HelpTip>
              This edits the <b>entry</b> — the set itself: name, number,
              pieces, theme. It doesn't touch what you own. Your copy's
              state — sealed, built, missing pieces, box or no box — lives
              on the small chip on the row, and the trash button deletes the
              whole entry.
            </HelpTip>
          </span>
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
            <TagEditor
              scope="lego"
              id={set.id}
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
          <TagChips tags={set.tags} />
          {/* your own words about the thing, not about one copy */}
          {set.notes && <p className="game-summary">{set.notes}</p>}
        </span>
      )}

      {editing !== null && (
        <span className="copy-edit">
          <button
            type="button"
            className={`toggle ${editVals.has_box ? "on" : ""}`}
            disabled={editVals.completeness === LEGO_NEEDS_BOX}
            title={
              editVals.completeness === LEGO_NEEDS_BOX
                ? "A sealed set is in its box by definition"
                : "Did you keep the box?"
            }
            onClick={() => setEditVals({ ...editVals, has_box: !editVals.has_box })}
          >
            {editVals.has_box ? "With box" : "No box"}
          </button>
          <select
            title="What you have"
            value={editVals.completeness}
            onChange={(e) => {
              const completeness = e.target.value;
              setEditVals((v) => ({
                ...v,
                completeness,
                has_box: completeness === LEGO_NEEDS_BOX ? true : v.has_box,
              }));
            }}
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
