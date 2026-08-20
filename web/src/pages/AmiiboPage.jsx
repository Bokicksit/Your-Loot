import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import EbayLink from "../components/EbayLink.jsx";
import HelpTip from "../components/HelpTip.jsx";
import { Icon } from "../components/Icons.jsx";
import { TagChips, TagEditor, TagFilter } from "../components/Tags.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import {
  AMIIBO_COMPLETENESS,
  LEGO_CONDITION,
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

/** amiibo — the second collection with a full catalogue behind it.
 *
 *  Cards set the pattern: every figure and card in the line is seeded into
 *  the shared catalogue, so adding one is searching what is already here and
 *  picking it — no external API at add time, no key, nothing to run out of.
 *  Manual entry stays for the figure the catalogue has never heard of, which
 *  at 932 seeded is the exception, not the path.
 */

const EMPTY_FORM = {
  title: "",
  character: "",
  amiibo_series: "",
  game_series: "",
  figure_type: "Figure",
  release_year: "",
  image_url: null,
  tags: [],
  notes: "",
  own: true,
  completeness: "boxed",
  condition: "used",
};

const copyLabel = (o) =>
  [
    o.completeness && shortFor(AMIIBO_COMPLETENESS, o.completeness),
    o.condition && labelFor(LEGO_CONDITION, o.condition),
  ]
    .filter(Boolean)
    .join(" · ");

export default function AmiiboPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({ series: [], types: [] });
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("amiibo");
  const [tileCols] = useTileCols("amiibo");
  const inlineDensity = useInlineDensity();
  const [seriesFilter, setSeriesFilter] = useListPref("amiibo", "seriesFilter", "");
  const [typeFilter, setTypeFilter] = useListPref("amiibo", "typeFilter", "");
  const [tagFilter, setTagFilter] = useListPref("amiibo", "tagFilter", "");
  // bumped whenever tags change, so the filter re-reads its counts
  const [tagsChanged, setTagsChanged] = useState(0);
  const [sort, setSort] = useListPref("amiibo", "sort", "series");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const activeFilters = [seriesFilter, typeFilter, tagFilter].filter(Boolean).length;
  // One write. Each useListPref setter rebuilds the whole prefs object
  // from its render-time copy, so several in a row undo each other.
  const { settings: allSettings, save: saveSettings } = useSettings();
  const clearFilters = () =>
    saveSettings({
      list_prefs: {
        ...(allSettings?.list_prefs || {}),
        amiibo: {
          ...(allSettings?.list_prefs?.amiibo || {}),
          seriesFilter: "",
          typeFilter: "",
          tagFilter: "",
        },
      },
    });
  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState("search"); // search -> details
  const [form, setForm] = useState(EMPTY_FORM);
  // the catalogue row the person picked; null means a manual entry
  const [picked, setPicked] = useState(null);
  const [results, setResults] = useState(null);
  const [seeded, setSeeded] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    const params = { sort };
    if (search) params.search = search;
    if (tagFilter) params.tag = tagFilter;
    if (seriesFilter) params.series = seriesFilter;
    if (typeFilter) params.figure_type = typeFilter;
    api
      .amiibo(params)
      .then((d) => {
        setItems(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    api.amiiboFacets().then((f) => {
      setFacets(f);
      if (seriesFilter && !f.series.some((t) => t.value === seriesFilter)) {
        setSeriesFilter("");
      }
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, seriesFilter, typeFilter, sort, tagFilter, tagsChanged]);

  const lookup = async (q) => {
    setSearching(true);
    setResults(null); // clear the old hits so the status stands alone
    try {
      const d = await api.amiiboSearch({ q });
      setResults(d.items);
      setSeeded(d.seeded);
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  const textSearch = () => {
    if (form.title.trim().length < 2) return;
    lookup(form.title.trim());
  };

  const pickResult = (r) => {
    // The catalogue row is the entry — nothing to create, only a copy to
    // add. The form keeps just what describes the copy.
    setPicked(r);
    setResults(null);
    setStep("details");
  };

  const openForm = () => {
    setForm(EMPTY_FORM);
    setPicked(null);
    setResults(null);
    setStep("search");
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setResults(null);
    setPicked(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      let target = picked;
      if (!target) {
        // hand entry: a prototype, a fake worth cataloguing as one, or a
        // figure newer than the seed
        target = await api.addAmiibo({
          title: form.title,
          character: form.character.trim() || null,
          amiibo_series: form.amiibo_series.trim() || null,
          game_series: form.game_series.trim() || null,
          figure_type: form.figure_type || null,
          release_year: form.release_year ? Number(form.release_year) : null,
          image_url: await api.localiseImage(form.image_url),
          notes: form.notes.trim() || null,
        });
      }
      if (form.tags.length) {
        await api.setItemTags(target.id, "amiibo", form.tags);
        setTagsChanged((n) => n + 1);
      }
      if (form.own) {
        await api.addOwned(target.id, {
          condition: form.condition,
          completeness: form.completeness,
        });
      } else {
        await api.addWanted(target.id);
      }
      const wantMode = !form.own;
      setForm(EMPTY_FORM);
      setPicked(null);
      setResults(null);
      setShowForm(false);
      if (wantMode) navigate("/wanted");
      else load();
    } catch (err) {
      alert(err.message);
    }
  };

  const patchItem = (id, status) =>
    setItems((xs) =>
      xs.map((x) =>
        x.id === id
          ? { ...x, owned: status.owned, wanted: status.wanted, tags: status.tags ?? x.tags }
          : x
      )
    );

  return (
    <div>
      <div className="toolbar">
        <label className="searchbox">
          <Icon id="search" />
          <input
            type="search"
            placeholder="Search figure, character or series…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <span className="count">{total}</span>
        </label>
        <button className="primary" onClick={openForm} title="Add an amiibo">
          <Icon id="plus" />
          Add
        </button>
      </div>

      <div className="chip-row">
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
        <ViewToggle module="amiibo" />
        {tiles && inlineDensity && <TileDensity module="amiibo" />}
      </div>
      {filtersOpen && (
        <div className="filter-sheet">
          <label>
            <span>Series</span>
            {facets.series.length > 0 && (
              <select
                className="chip-select"
                value={seriesFilter}
                onChange={(e) => setSeriesFilter(e.target.value)}
              >
                <option value="">All series</option>
                {facets.series.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.value} ({t.count})
                  </option>
                ))}
              </select>
            )}
          </label>
          <label>
            <span>Type</span>
            {facets.types.length > 0 && (
              <select
                className="chip-select"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
              >
                <option value="">All types</option>
                {facets.types.map((t) => (
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
              scope="amiibo"
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
              <option value="series">By series</option>
              <option value="title">A–Z</option>
              <option value="character">By character</option>
              <option value="year">By year</option>
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
      {tiles && !inlineDensity && <TileDensity module="amiibo" />}

      <AddSheet
        open={showForm && step === "search"}
        title="Find an amiibo"
        onClose={closeForm}
        help={
          <>
            The whole line is already catalogued — every figure and card. A
            character, a game or a series name all work (<b>Ganondorf</b>,{" "}
            <b>Splatoon</b>…); pick yours from the matches and its picture
            and facts come along. <b>Enter it by hand</b> is there for
            customs and oddities.
          </>
        }
      >
        <div className="form-row">
          <input
            type="text"
            required
            className="grow"
            placeholder="Figure, character or series (Ganondorf, Splatoon…)"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
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
              {results.length} match{results.length === 1 ? "" : "es"} in the catalogue
            </span>
            {results.length === 0 && (
              <p className="empty" style={{ padding: "var(--s-3)" }}>
                {seeded
                  ? "Nothing in the catalogue by that name — fill it in by hand below."
                  : "The amiibo catalogue has not been seeded on this server yet — ask whoever runs it to run seed_amiibo.py. Hand entry works meanwhile."}
              </p>
            )}
            <div className="grid pick-grid">
              {results.map((r) => (
                <div
                  key={r.id}
                  className="tile pick"
                  onClick={() => pickResult(r)}
                  title="This one"
                >
                  {r.image_url ? (
                    <img src={r.image_url} alt={r.title} loading="lazy" />
                  ) : (
                    <div className="placeholder" data-label="no photo" />
                  )}
                  <div className="tile-info">
                    <strong>{r.title}</strong>
                    <small>{r.attrs.amiibo_series}</small>
                    <small>
                      {[r.attrs.figure_type, r.attrs.release_year]
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
        title={picked ? "Add your copy" : "Add an amiibo"}
        onClose={closeForm}
        onBack={() => {
          setPicked(null);
          setStep("search");
        }}
        help={
          <>
            The catalogue already knows the figure — what's left to say is
            about <b>your copy</b>: boxed or loose, its condition, a note.
            <b> I own it</b> puts it on the shelf; <b>I want it</b> files a
            wish instead. Everything stays editable later.
          </>
        }
      >
        <form className="add-form" onSubmit={submit}>
          {picked ? (
            // The catalogue already knows the figure; only the copy is yours
            // to describe. Repeating its fields as editable boxes here would
            // invite retyping shared facts nobody should have to retype.
            <div className="form-row">
              {picked.image_url ? (
                <img
                  src={picked.image_url}
                  alt=""
                  style={{ width: 54, height: 54, objectFit: "contain" }}
                />
              ) : (
                <span className="game-icon">
                  <Icon id="fig" />
                </span>
              )}
              <span className="game-text">
                <strong>{picked.title}</strong>
                <small className="game-meta">
                  {picked.attrs.amiibo_series && <span>{picked.attrs.amiibo_series}</span>}
                  {picked.attrs.figure_type && <span>{picked.attrs.figure_type}</span>}
                  {picked.attrs.release_year && <span>{picked.attrs.release_year}</span>}
                </small>
              </span>
            </div>
          ) : (
            <>
              <div className="form-row">
                <input
                  type="text"
                  required
                  className="grow"
                  placeholder="Name as you want it filed"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
              </div>
              <div className="form-row">
                <input
                  type="text"
                  className="grow"
                  placeholder="Character"
                  value={form.character}
                  onChange={(e) => setForm({ ...form, character: e.target.value })}
                />
                <input
                  type="text"
                  className="grow"
                  placeholder="amiibo series (Super Smash Bros.…)"
                  value={form.amiibo_series}
                  onChange={(e) => setForm({ ...form, amiibo_series: e.target.value })}
                />
              </div>
              <div className="form-row">
                <select
                  title="What kind of amiibo"
                  value={form.figure_type}
                  onChange={(e) => setForm({ ...form, figure_type: e.target.value })}
                >
                  {["Figure", "Card", "Yarn", "Band"].map((t) => (
                    <option key={t} value={t}>
                      {t}
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
                <ImagePicker
                  value={form.image_url}
                  label="Photo"
                  onChange={(url) => setForm({ ...form, image_url: url })}
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
            </>
          )}
          {/* last of the fields: a tag is what you think of once the rest
              is filled in */}
          <div className="form-row">
            <TagEditor
              scope="amiibo"
              value={form.tags}
              onChange={(tags) => setForm({ ...form, tags })}
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
              title="In the box, or out of it?"
              value={form.completeness}
              onChange={(e) => setForm({ ...form, completeness: e.target.value })}
            >
              {AMIIBO_COMPLETENESS.map(([v, l]) => (
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
      {!error && loaded && items.length === 0 && (
        <div className="empty">
          <span className="glyph">
            <Icon id="fig" />
          </span>
          <strong>No amiibo yet</strong>
          <p>Search the catalogue by figure, character or series — all 932 are in it.</p>
        </div>
      )}

      <div
        className={`game-list ${tiles ? `as-tiles cols-${tileCols}` : ""}`}
        style={tiles ? { "--tile-cols": tileCols } : undefined}
      >
        {items.map((x) => (
          <AmiiboRow
            key={x.id}
            item={x}
            onChange={patchItem}
            onReload={load}
            onTagsChanged={() => setTagsChanged((n) => n + 1)}
          />
        ))}
      </div>
    </div>
  );
}

function AmiiboRow({ item, onChange, onReload, onTagsChanged }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editVals, setEditVals] = useState({ completeness: "boxed", condition: "used" });
  const [infoOpen, setInfoOpen] = useState(false);
  const a = item.attrs;
  // A catalogue row is everybody's: your copies are yours to manage, the row
  // itself is not yours to delete, and its facts are not yours to retype.
  const fromCatalogue = !!a.amiibo_id;

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      onChange(item.id, await fn());
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeCopy = (o) => {
    if (!confirm(`Remove this copy of ${item.title} (${copyLabel(o) || "copy"})?`)) return;
    run(() => api.removeOwned(item.id, o.id));
  };
  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      completeness: o.completeness || "boxed",
      condition: o.condition || "used",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const s = await api.updateOwned(item.id, editing, editVals);
      setEditing(null);
      return s;
    });

  const del = async () => {
    if (!confirm(`Delete "${item.title}" and its copies?`)) return;
    await api.deleteAmiibo(item.id);
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
    () => keepOpen(entry, entryInit.current, entry !== null, item.title)
  );
  const openEntry = () => {
    const vals = {
      title: item.title || "",
      character: a.character || "",
      amiibo_series: a.amiibo_series || "",
      game_series: a.game_series || "",
      figure_type: a.figure_type || "",
      release_year: a.release_year ?? "",
      image_url: item.image_url,
      tags: item.tags || [],
      notes: item.notes || "",
    };
    entryInit.current = vals;
    setEntry(vals);
  };

  const saveEntry = async () => {
    if (busy) return;
    if (!entry.title.trim()) return alert("It needs a name.");
    setBusy(true);
    try {
      await api.updateAmiibo(item.id, {
        title: entry.title.trim(),
        character: entry.character.trim() || null,
        amiibo_series: entry.amiibo_series.trim() || null,
        game_series: entry.game_series.trim() || null,
        figure_type: entry.figure_type.trim() || null,
        release_year: entry.release_year ? Number(entry.release_year) : null,
        image_url: await api.localiseImage(entry.image_url),
        notes: entry.notes.trim() || null,
      });
      // Staged with the rest of the form, so Cancel discards a tag the
      // same way it discards a retyped title.
      await api.setItemTags(item.id, "amiibo", entry.tags);
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
      className={`game-row ${item.owned.length ? "row-owned" : ""} ${infoOpen || entry ? "open" : ""}`}
    >
      {item.image_url ? (
        <img
          className="game-cover contain"
          src={item.image_url}
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
          <Icon id="fig" />
        </span>
      )}
      <span className="game-text" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
        <strong>{item.title}</strong>
        <small className="game-meta">
          {a.amiibo_series && <span className="plat-badge">{a.amiibo_series}</span>}
          {a.figure_type && <span>{a.figure_type}</span>}
          {a.release_year && <span>{a.release_year}</span>}
        </small>
        {item.owned.length > 0 && (
          <span className="copy-chips">
            {item.owned.map((o) => (
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
        {/* a catalogue row is everybody's — removing your copies is done on
            the chips, and the row stays for the next person */}
        {!fromCatalogue && (
          <button className="ghost icon danger" onClick={del} title="Delete entry">
            <Icon id="trash" />
          </button>
        )}
      </span>

      {entry && (
        <span className="entry-edit">
          <span className="game-info-line">
            amiibo details
            <HelpTip>
              This edits the <b>entry</b> — the figure itself: name,
              character, series. It doesn't touch what you own. Your copy —
              boxed or loose, its condition — lives on the small chip on the
              row, and the trash button deletes the whole entry.
            </HelpTip>
          </span>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Name"
              value={entry.title}
              onChange={(e) => setEntry({ ...entry, title: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Character"
              value={entry.character}
              onChange={(e) => setEntry({ ...entry, character: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="amiibo series"
              value={entry.amiibo_series}
              onChange={(e) => setEntry({ ...entry, amiibo_series: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Game series"
              value={entry.game_series}
              onChange={(e) => setEntry({ ...entry, game_series: e.target.value })}
            />
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
            <TagEditor
              scope="amiibo"
              id={item.id}
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
              label="Photo"
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
            {item.image_url && (
              <img className="expand-cover contain" src={item.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{item.title}</span>
              <span className="expand-sub">
                {[a.character, a.amiibo_series].filter(Boolean).join(" · ") || "amiibo"}
              </span>
              <span className="game-info-line">
                {[
                  a.figure_type,
                  a.game_series && `${a.game_series} series`,
                  a.release_na || a.release_year,
                ]
                  .filter(Boolean)
                  .join("  ·  ")}
              </span>
            </div>
            {/* series + "amiibo" is how they are listed for sale — the name
                alone pulls up plush toys and posters */}
            <EbayLink title={item.title} terms={[a.amiibo_series, "amiibo"]} />
          </div>
          <TagChips tags={item.tags} />
          {/* your own words about the thing, not about one copy */}
          {item.notes && <p className="game-summary">{item.notes}</p>}
        </span>
      )}

      {editing !== null && (
        <span className="copy-edit">
          <select
            title="In the box, or out of it?"
            value={editVals.completeness}
            onChange={(e) => setEditVals({ ...editVals, completeness: e.target.value })}
          >
            {withUnknown(AMIIBO_COMPLETENESS, editVals.completeness).map(([v, l]) => (
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
