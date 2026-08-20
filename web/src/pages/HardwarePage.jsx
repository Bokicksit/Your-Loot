import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import ArtOptions from "../components/ArtOptions.jsx";
import AddSheet from "../components/AddSheet.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import HelpTip, { ShelfHelp } from "../components/HelpTip.jsx";
import { Icon } from "../components/Icons.jsx";
import { TagChips, TagEditor, TagFilter } from "../components/Tags.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { useSettings, useListPref } from "../settings.jsx";
// cleanTitle, not cleanGameTitle: the game cleaner cuts a title at the first
// platform name, which is right for "Zelda for Nintendo Switch" and ruinous
// here, where the platform name IS the product — it turned "Super Nintendo
// SNES Console" into "Super". This one strips brackets and condition words
// and leaves the name alone.
import { cleanTitle } from "../upc.js";
import ViewToggle, {
  useTileView,
  useTileCols,
  useInlineDensity,
  TileDensity,
} from "../components/ViewToggle.jsx";

const REGIONS = ["NTSC-U", "PAL", "NTSC-J", "Region-free"];
const CONDITIONS = ["Mint", "Good", "Fair", "Poor"];
const COMPLETENESS = ["loose", "CIB", "sealed"];
const WORKING = ["works", "partial", "broken", "untested"];

const EMPTY_FORM = {
  title: "",
  // console | controller | accessory — the first question a manual entry
  // answers, and the sub-shelf the list can filter by
  hardware_kind: "console",
  platform_id: "",
  region: "NTSC-U",
  model_number: "",
  serial_number: "",
  working: "works",
  image_url: null,
  tags: [],
  notes: "",
  own: true,
  completeness: "loose", // consoles are usually out of box
  condition: "Good",
};

// A keyword search of a shop database is a search of everything that shop
// sells, so "game boy advance" returns mostly cartridges — every GBA game has
// "Game Boy Advance" written on it. The database's own category is no help:
// it files Crash Bandicoot under "Video Game Consoles".
//
// So the listings are ranked rather than filtered. Ranked, because this data
// is messy enough that a hard rule would eventually hide the one console in a
// page of games; the machines come first and the cartridges are still there
// underneath if the guess was wrong.
const HARDWARE_WORDS =
  /(console|system|handheld|controller|gamepad|joystick|dock|charger|adapter|power supply|cable|unit|bundle|refurb\w*|oem)/i;
// AGS-001, SCPH-70012, HDH-001 — a cartridge does not have one of these
const HARDWARE_MODEL = /[A-Z]{2,4}-[A-Z0-9]{3,7}/;
const SOFTWARE_CATEGORY = /video game software|games?\s*>/i;

function hardwareScore(r) {
  const t = r.title || "";
  let score = 0;
  if (HARDWARE_WORDS.test(t)) score += 2;
  if (HARDWARE_MODEL.test(t)) score += 2;
  if (r.model && !/^\d{11,14}$/.test(r.model)) score += 1;
  if (SOFTWARE_CATEGORY.test(r.category || "")) score -= 3;
  return score;
}

// The listing's own model field when the seller filled it in, else the
// SCPH-70012 / SNS-001 shape out of the title. Letters-then-digits with a
// hyphen is specific enough not to catch "Model 2" or a year, and it is how
// Sony, Nintendo and Sega all number their hardware.
const MODEL_IN_TITLE = /([A-Z]{2,4}-[A-Z0-9]{3,7})/;

// Sellers put whatever they like in the model field — one PS2 listing had the
// product's own barcode in it. A bare run of 11-14 digits is a UPC or an EAN,
// never a model number, so it is ignored in favour of reading the title.
const LOOKS_LIKE_A_BARCODE = /^\d{11,14}$/;

function modelFrom(r) {
  const listed = (r.model || "").trim();
  if (listed && listed.length <= 50 && !LOOKS_LIKE_A_BARCODE.test(listed)) return listed;
  return (r.title || "").match(MODEL_IN_TITLE)?.[1] || "";
}

// Hardware: consoles + accessories. Same data module as games under the hood
// (is_hardware=true), its own tab and per-unit fields up here.
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

export default function HardwarePage() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [platforms, setPlatforms] = useState([]);
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("hardware");
  const [tileCols] = useTileCols("hardware");
  const inlineDensity = useInlineDensity();
  const [platformFilter, setPlatformFilter] = useListPref("hardware", "platformFilter", "");
  const [kindFilter, setKindFilter] = useListPref("hardware", "kindFilter", "");
  const [tagFilter, setTagFilter] = useListPref("hardware", "tagFilter", "");
  // bumped whenever tags change, so the filter re-reads its counts
  const [tagsChanged, setTagsChanged] = useState(0);
  const [sort, setSort] = useListPref("hardware", "sort", "title");
  // Shown while you fill the form in, not thrown at you on save.
  const [dupe, setDupe] = useState(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  // sort is not counted: it never hides anything, and a badge for the
  // order you always use would announce a problem that is not there
  const activeFilters = [platformFilter, kindFilter, tagFilter].filter(Boolean).length;
  // One write. Each useListPref setter rebuilds the whole prefs object
  // from its render-time copy, so several in a row undo each other.
  const { settings: allSettings, save: saveSettings } = useSettings();
  const clearFilters = () =>
    saveSettings({
      list_prefs: {
        ...(allSettings?.list_prefs || {}),
        hardware: {
          ...(allSettings?.list_prefs?.hardware || {}),
            platformFilter: "",
            kindFilter: "",
            tagFilter: "",
        },
      },
    });
  const [showForm, setShowForm] = useState(false);
  const { settings } = useSettings();
  // a blank form starts at whatever region you told Settings you mostly buy
  const blankForm = () => ({
    ...EMPTY_FORM,
    region: settings?.default_region || EMPTY_FORM.region,
  });
  const [form, setForm] = useState(blankForm);
  const [art, setArt] = useState([]); // retailer photos from a scanned box
  const [results, setResults] = useState(null); // null = nothing searched yet
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  // hits from the seeded console catalogue, offered as you type the name
  const [catalogue, setCatalogue] = useState([]);
  // a pick fills the form; stop re-searching what the pick just wrote
  const [picked, setPicked] = useState(false);

  // A boxed console or controller carries a UPC like any other product, so the
  // same lookup games and movies use fills the name and offers photos of the
  // actual box. Loose retro hardware has no barcode — that stays typed in.
  // The same retail database the scanner reads, asked by name instead of by
  // number. Retro hardware is not in any games catalogue — IGDB knows the
  // Zelda cartridge and nothing about the console — but a shop has sold one,
  // and a shop listing carries a photograph of the actual unit.
  //
  // Explicit, never automatic: it shares the barcode service's daily budget,
  // and typing a name is not on its own a request to spend one.
  const nameSearch = async () => {
    // Both, when both are known. A model number is the most specific thing
    // about a console — SNS-001 is one revision of the SNES and SNS-101 is
    // another — and a shop that lists it usually puts it in the title, so it
    // narrows a search that "Super Nintendo" alone floods.
    const term = [form.title.trim(), form.model_number.trim()]
      .filter(Boolean)
      .join(" ");
    if (term.length < 3 || searching) return;
    setSearching(true);
    setResults(null); // clear the old hits so the status stands alone
    try {
      const { items, exhausted } = await api.productSearch(term, false);
      if (exhausted) alert("The lookup service is out of requests for today.");
      // stable sort: equal scores keep the order the shop returned them in
      const ranked = (items || [])
        .map((r, i) => ({ r, i, score: hardwareScore(r) }))
        .sort((a, b) => b.score - a.score || a.i - b.i)
        .map((x) => x.r);
      setResults(ranked);
    } catch (e) {
      alert(e.message);
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  // A pick fills the name and offers its photographs; everything else about a
  // console — model, serial, whether it works — is on the unit in your hands.
  const pickResult = (r) => {
    const shots = (r.images || []).map((url) => ({ url, kind: "box" }));
    setArt(shots);
    setForm((f) => ({
      ...f,
      title: cleanTitle(r.title) || r.title,
      // Never overwrite one you typed: you read yours off the actual machine,
      // and a listing is describing some other person's.
      model_number: f.model_number.trim() || modelFrom(r) || "",
      image_url: shots[0]?.url || f.image_url,
    }));
    setResults(null);
  };

  const onBarcode = async (code) => {
    try {
      const res = await api.barcodeLookup(code);
      if (!res.found) {
        alert("No product match for that barcode — type the name instead.");
        return;
      }
      const raw = res.titles[0].title;
      const boxArt = (res.titles[0].images || []).map((url) => ({ url, kind: "box" }));
      setArt(boxArt);
      setForm((f) => ({
        ...f,
        title: cleanTitle(raw) || raw,
        // the scan carried this all along and was dropping it on the floor
        model_number: f.model_number.trim() || modelFrom(res.titles[0]) || "",
        image_url: boxArt[0]?.url || f.image_url,
      }));
    } catch (e) {
      alert(e.message);
    }
  };
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.platforms().then(setPlatforms);
  }, []);

  const load = () => {
    const params = { is_hardware: true, sort, limit: 200 };
    if (search) params.search = search;
    if (tagFilter) params.tag = tagFilter;
    if (platformFilter) params.platform_id = platformFilter;
    if (kindFilter) params.hardware_kind = kindFilter;
    api
      .games(params)
      .then((d) => {
        setRows(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    if (!showForm) return setDupe(null);
    const t = setTimeout(
      () => duplicateNotice("hardware", form.title).then(setDupe),
      350
    );
    return () => clearTimeout(t);
  }, [showForm, form.title]);

  // The seeded catalogue, asked as you type. Local and keyless, so it can
  // afford to run on every pause — unlike the shop lookup, which spends a
  // budget and therefore stays behind its button.
  useEffect(() => {
    if (!showForm || picked || form.title.trim().length < 2) {
      setCatalogue([]);
      return;
    }
    const t = setTimeout(
      () =>
        api
          .hardwareCatalogue({ q: form.title.trim(), limit: 6 })
          .then((d) => setCatalogue(d.items || []))
          .catch(() => setCatalogue([])), // no catalogue is not an error
      250
    );
    return () => clearTimeout(t);
  }, [showForm, form.title, picked]);

  // Everything the catalogue knows lands in the form; serial number and
  // working state stay yours, because they belong to the unit on the shelf.
  const pickCatalogue = (item) => {
    const a = item.attrs || {};
    if (a.platform_id && !platforms.some((p) => p.id === a.platform_id)) {
      api.platforms().then(setPlatforms); // seeded after this page loaded
    }
    setForm((f) => ({
      ...f,
      title: item.title,
      hardware_kind: a.hardware_kind || f.hardware_kind,
      platform_id: a.platform_id ? String(a.platform_id) : f.platform_id,
      model_number: a.model_number || f.model_number,
      region: "NTSC-U", // it is the North American dataset
      image_url: item.image_url || f.image_url,
    }));
    setCatalogue([]);
    setPicked(true);
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, platformFilter, kindFilter, sort, tagFilter, tagsChanged]);

  // settings arrive after mount, so the default region is picked up on open
  const openForm = () => {
    setForm(blankForm());
    setArt([]);
    setResults(null);
    setCatalogue([]);
    setPicked(false);
    setShowForm(true);
  };

  const closeForm = () => setShowForm(false);

  const submit = async (e) => {
    e.preventDefault();
    try {
      const created = await api.addGame({
        title: form.title,
        platform_id: form.platform_id ? Number(form.platform_id) : null,
        region: form.region || null,
        is_hardware: true,
        hardware_kind: form.hardware_kind || null,
        model_number: form.model_number.trim() || null,
        serial_number: form.serial_number.trim() || null,
        working: form.working,
        image_url: await api.localiseImage(form.image_url),
        notes: form.notes.trim() || null,
      });
      // after the create, because a tag needs something to hang on
      if (form.tags.length) {
        await api.setItemTags(created.id, "hardware", form.tags);
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
      setForm(blankForm());
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

  const patchRow = (id, status) =>
    setRows((rs) =>
      rs.map((r) =>
        r.id === id ? { ...r, owned: status.owned, wanted: status.wanted, tags: status.tags ?? hw.tags } : r
      )
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
            placeholder="Search hardware…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <span className="count">{total}</span>
        </label>
        <button className="primary" onClick={openForm} title="Add hardware">
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
        <ViewToggle module="hardware" />
        {tiles && inlineDensity && <TileDensity module="hardware" />}
        <ShelfHelp noun="a machine" />
      </div>
      {filtersOpen && (
        <div className="filter-sheet">
          <label>
            <span>System</span>
          <select
            className="chip-select"
            title="Filter by system"
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
          >
            <option value="">All systems</option>
            {platforms.map((p) => (
              <option key={p.id} value={p.id}>
                {p.abbreviation || p.name}
              </option>
            ))}
          </select>
          </label>
          <label>
            <span>Kind</span>
            <select
              className="chip-select"
              title="Filter by kind"
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
            >
              <option value="">All kinds</option>
              <option value="console">Consoles</option>
              <option value="controller">Controllers</option>
              <option value="accessory">Accessories</option>
              <option value="unsorted">Unsorted</option>
            </select>
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
            <option value="platform">By system</option>
            <option value="added">Last added</option>
            <option value="oldest">First added</option>
          </select>
          </label>
          <label>
            <span>Tag</span>
          <TagFilter
            scope="hardware"
            value={tagFilter}
            onChange={setTagFilter}
            reloadKey={tagsChanged}
          />
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
      {tiles && !inlineDensity && <TileDensity module="hardware" />}

      {/* No games catalogue knows retro hardware, so this asks the retail
          database the scanner uses — by name when you have no box to scan.
          Still one step: the search is a shortcut on the form, not a gate
          in front of it. */}
      <AddSheet
        open={showForm}
        title="Add hardware"
        onClose={closeForm}
        help={
          <>
            Start typing and the built-in <b>console catalogue</b> answers —
            machines, famous colourways, controllers, accessories — so a
            known variant is picked, not typed. The <b>serial number</b> and
            whether it <b>works</b> are yours to record; they belong to the
            unit on your shelf, not the catalogue.
          </>
        }
      >
        <form className="add-form" onSubmit={submit}>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Name (Super Nintendo)"
              value={form.title}
              onChange={(e) => {
                setPicked(false); // a changed name reopens the suggestions
                setForm({ ...form, title: e.target.value });
              }}
            />
            <button
              type="button"
              className="ghost icon"
              title="Search shop listings by name"
              onClick={nameSearch}
              disabled={searching || form.title.trim().length < 3}
            >
              <Icon id="search" />
            </button>
            <BarcodeScan onCode={onBarcode} />
          </div>
          {catalogue.length > 0 && (
            <>
              {/* the built-in catalogue answers first — a known variant
                  fills the whole form, not just the name */}
              <p className="pick-label">From the console catalogue:</p>
              <div className="grid pick-grid">
                {catalogue.map((c) => (
                  <div
                    key={c.id}
                    className="tile pick square"
                    onClick={() => pickCatalogue(c)}
                    title="Use this catalogue entry"
                  >
                    {c.image_url ? (
                      <img src={c.image_url} alt={c.title} loading="lazy" />
                    ) : (
                      <div className="placeholder" data-label="no photo" />
                    )}
                    <div className="tile-info">
                      <strong>{c.title}</strong>
                      <small>
                        {[c.attrs?.model_number, c.attrs?.release_year]
                          .filter(Boolean)
                          .join(" · ") || c.attrs?.hardware_kind}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          {searching && (
            <p className="empty" style={{ padding: "var(--s-3)" }}>Looking…</p>
          )}
          {results !== null && !searching && (
            <>
              {results.length === 0 ? (
                <p className="empty" style={{ padding: "var(--s-3)" }}>
                  Nothing found by that name — the fields below still work.
                </p>
              ) : (
                <div className="grid pick-grid">
                  {results.slice(0, 8).map((r, i) => (
                    <div
                      key={i}
                      className="tile pick square"
                      onClick={() => pickResult(r)}
                      title="Use this listing's name and photos"
                    >
                      {r.images?.[0] ? (
                        <img src={r.images[0]} alt={r.title} loading="lazy" />
                      ) : (
                        <div className="placeholder" data-label="no photo" />
                      )}
                      <div className="tile-info">
                        <strong>{r.title}</strong>
                        <small>{r.brand || "—"}</small>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
          <div className="form-row">
            <select
              value={form.platform_id}
              onChange={(e) => setForm({ ...form, platform_id: e.target.value })}
            >
              <option value="">Platform…</option>
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <select
              value={form.region}
              onChange={(e) => setForm({ ...form, region: e.target.value })}
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
              placeholder="Model (SNS-001)"
              value={form.model_number}
              onChange={(e) => setForm({ ...form, model_number: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Serial number"
              value={form.serial_number}
              onChange={(e) => setForm({ ...form, serial_number: e.target.value })}
            />
            {/* The label on the underside is a barcode too — usually Code 128,
                which this already reads. Its own button, because a scan next
                to the name means a product and a scan next to the serial
                means this, and guessing between them would be worse than
                either. */}
            <BarcodeScan
              onCode={(code) => setForm((f) => ({ ...f, serial_number: code }))}
              title="Scan the serial number"
              numeric={false}
            />
          </div>
          <div className="form-row">
            <select
              title="What kind of hardware"
              value={form.hardware_kind}
              onChange={(e) => setForm({ ...form, hardware_kind: e.target.value })}
            >
              <option value="console">Console</option>
              <option value="controller">Controller</option>
              <option value="accessory">Accessory</option>
            </select>
            <select
              title="Working status"
              value={form.working}
              onChange={(e) => setForm({ ...form, working: e.target.value })}
            >
              {WORKING.map((w) => (
                <option key={w}>{w}</option>
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
              label="Photo"
              onChange={(url) => setForm({ ...form, image_url: url })}
            />
          </div>
          {dupe && <p className="dupe-note">{dupe}</p>}
          {/* last of the fields: a tag is what you think of once the rest
              is filled in */}
          <div className="form-row">
            <TagEditor
              scope="hardware"
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
              disabled={!form.own}
              value={form.completeness}
              onChange={(e) => setForm({ ...form, completeness: e.target.value })}
            >
              {COMPLETENESS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <select
              disabled={!form.own}
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
      {!error && loaded && rows.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="console" /></span>
          <strong>No hardware yet</strong>
          <p>Consoles, controllers, cables — hit Add to start the setup shelf.</p>
        </div>
      )}

      <div
        className={`game-list ${tiles ? `as-tiles cols-${tileCols}` : ""}`}
        style={tiles ? { "--tile-cols": tileCols } : undefined}
      >
        {rows.map((h) => (
          <HardwareRow
            key={h.id}
            hw={h}
            platforms={platforms}
            onChange={patchRow}
            onReload={load}
            onTagsChanged={() => setTagsChanged((n) => n + 1)}
          />
        ))}
      </div>
    </div>
  );
}

function HardwareRow({ hw, platforms, onChange, onReload , onTagsChanged}) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // owned copy id
  const [editVals, setEditVals] = useState({ completeness: "loose", condition: "Good" });
  const [entryOpen, setEntryOpen] = useState(false);
  const [entry, setEntry] = useState({});
  const [infoOpen, setInfoOpen] = useState(false);
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
    () => keepOpen(entry, entryInit.current, entryOpen, hw.title),
  );

  const a = hw.attrs;

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      const status = await fn();
      onChange(hw.id, status);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeCopy = (o) => {
    const label = [o.completeness, o.condition].filter(Boolean).join(" · ") || "unit";
    if (!confirm(`Remove this unit of ${hw.title} (${label})?`)) return;
    run(() => api.removeOwned(hw.id, o.id));
  };
  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      completeness: o.completeness || "loose",
      condition: o.condition || "Good",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const status = await api.updateOwned(hw.id, editing, editVals);
      setEditing(null);
      return status;
    });

  const openEntry = () => {
    const vals = {
      title: hw.title,
      hardware_kind: a.hardware_kind || "",
      platform_id: a.platform_id ? String(a.platform_id) : "",
      region: a.region || "",
      model_number: a.model_number || "",
      serial_number: a.serial_number || "",
      working: a.working || "works",
      image_url: hw.image_url,
      tags: hw.tags || [],
      notes: hw.notes || "",
    };
    entryInit.current = vals;
    setEntry(vals);
    setEntryOpen(true);
  };
  const saveEntry = async () => {
    if (busy || !entry.title.trim()) return;
    setBusy(true);
    try {
      await api.updateGame(hw.id, {
        hardware_kind: entry.hardware_kind || null,
        title: entry.title.trim(),
        platform_id: entry.platform_id ? Number(entry.platform_id) : null,
        region: entry.region || null,
        model_number: entry.model_number.trim() || null,
        serial_number: entry.serial_number.trim() || null,
        working: entry.working,
        image_url: await api.localiseImage(entry.image_url),
        notes: entry.notes.trim() || null,
      });
      // Staged with the rest of the form, so Cancel discards a tag the
      // same way it discards a retyped title.
      await api.setItemTags(hw.id, "hardware", entry.tags);
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
    if (!confirm(`Delete "${hw.title}" and its records?`)) return;
    await api.deleteGame(hw.id);
    onReload();
  };

  return (
    <div
      ref={rowRef}
      className={`game-row ${hw.owned.length ? "row-owned" : ""} ${infoOpen || entryOpen ? "open" : ""}`}
    >
      {hw.image_url ? (
        <img
          className="game-cover"
          src={hw.image_url}
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
          <Icon id="console" />
        </span>
      )}
      <span
        className="game-text"
        style={{ cursor: "pointer" }}
        onClick={() => setInfoOpen(!infoOpen)}
      >
        <strong>{hw.title}</strong>
        <small className="game-meta">
          {a.platform_abbr && <span className="plat-badge">{a.platform_abbr}</span>}
          {a.hardware_kind && <span className="kind-badge">{a.hardware_kind}</span>}
          {a.model_number && <span>{a.model_number}</span>}
          {a.working && <span className={`hw-status ${a.working}`}>{a.working}</span>}
        </small>
        {hw.owned.length > 0 && (
          <span className="copy-chips">
            {hw.owned.map((o) => (
              <span
                key={o.id}
                className="chip copy"
                onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
                title="Edit this unit"
              >
                <Icon id="pencil" />
                {[o.completeness, o.condition].filter(Boolean).join(" · ") || "set condition…"}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeCopy(o);
                  }}
                  title="Remove this unit"
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
            <div className="expand-body">
              <span className="expand-title">{hw.title}</span>
              <span className="expand-sub">
                {[a.platform_name, a.region, a.model_number]
                  .filter(Boolean)
                  .join(" · ") || "No system set"}
              </span>
              <span className="game-info-line">
                {[
                  a.working && `Status: ${a.working}`,
                  a.serial_number && `S/N ${a.serial_number}`,
                ]
                  .filter(Boolean)
                  .join("  ·  ")}
              </span>
            </div>
            {/* the model number is what separates an original from a revision,
                and it's the one thing hardware sellers do write down */}
            <EbayLink title={hw.title} terms={[a.model_number, a.platform_name]} />
          </div>
          <TagChips tags={hw.tags} />
          {/* your own words about the thing, not about one copy */}
          {hw.notes && <p className="game-summary">{hw.notes}</p>}
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

      {entryOpen && (
        <span className="entry-edit">
          <span className="game-info-line">
            Hardware details
            <HelpTip>
              Everything about this unit — name, model, <b>serial number</b>{" "}
              and whether it <b>works</b> — is edited here; hardware is
              one-of-a-kind, so the unit and the entry are the same thing.
              Its condition sits on the small chip on the row, and the trash
              button deletes it entirely.
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
              value={entry.platform_id}
              onChange={(e) => setEntry({ ...entry, platform_id: e.target.value })}
            >
              <option value="">Platform…</option>
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <select
              value={entry.region}
              onChange={(e) => setEntry({ ...entry, region: e.target.value })}
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
              placeholder="Model"
              value={entry.model_number}
              onChange={(e) => setEntry({ ...entry, model_number: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Serial"
              value={entry.serial_number}
              onChange={(e) => setEntry({ ...entry, serial_number: e.target.value })}
            />
            <BarcodeScan
              onCode={(code) => setEntry((v) => ({ ...v, serial_number: code }))}
              title="Scan the serial number"
              numeric={false}
            />
          </div>
          <div className="form-row">
            <select
              title="What kind of hardware"
              value={entry.hardware_kind}
              onChange={(e) => setEntry({ ...entry, hardware_kind: e.target.value })}
            >
              <option value="">Unsorted</option>
              <option value="console">Console</option>
              <option value="controller">Controller</option>
              <option value="accessory">Accessory</option>
            </select>
            <select
              value={entry.working}
              onChange={(e) => setEntry({ ...entry, working: e.target.value })}
            >
              {WORKING.map((w) => (
                <option key={w}>{w}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <TagEditor
              scope="hardware"
              id={hw.id}
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
              label="Unit photo"
              onChange={(url) => setEntry({ ...entry, image_url: url })}
            />
            <button
              className="primary icon"
              style={{ marginLeft: "auto" }}
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
    </div>
  );
}
