import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import ArtOptions from "../components/ArtOptions.jsx";
import AddSheet from "../components/AddSheet.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { Icon } from "../components/Icons.jsx";
import { TagChips, TagEditor, TagFilter } from "../components/Tags.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { useSettings, useListPref } from "../settings.jsx";
import { cleanGameTitle } from "../upc.js";
import ViewToggle, { useTileView } from "../components/ViewToggle.jsx";

const REGIONS = ["NTSC-U", "PAL", "NTSC-J", "Region-free"];
const CONDITIONS = ["Mint", "Good", "Fair", "Poor"];
const COMPLETENESS = ["loose", "CIB", "sealed"];
const WORKING = ["works", "partial", "broken", "untested"];

const EMPTY_FORM = {
  title: "",
  platform_id: "",
  region: "NTSC-U",
  model_number: "",
  serial_number: "",
  working: "works",
  parent_id: "",
  image_url: null,
  tags: [],
  own: true,
  completeness: "loose", // consoles are usually out of box
  condition: "Good",
};

// Hardware: consoles + accessories. Same data module as games under the hood
// (is_hardware=true), its own tab and per-unit fields up here.
export default function HardwarePage() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [platforms, setPlatforms] = useState([]);
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("hardware");
  const [platformFilter, setPlatformFilter] = useListPref("hardware", "platformFilter", "");
  const [tagFilter, setTagFilter] = useListPref("hardware", "tagFilter", "");
  // bumped whenever tags change, so the filter re-reads its counts
  const [tagsChanged, setTagsChanged] = useState(0);
  const [sort, setSort] = useListPref("hardware", "sort", "title");
  const [showForm, setShowForm] = useState(false);
  const { settings } = useSettings();
  // a blank form starts at whatever region you told Settings you mostly buy
  const blankForm = () => ({
    ...EMPTY_FORM,
    region: settings?.default_region || EMPTY_FORM.region,
  });
  const [form, setForm] = useState(blankForm);
  const [art, setArt] = useState([]); // retailer photos from a scanned box
  const [error, setError] = useState(null);

  // A boxed console or controller carries a UPC like any other product, so the
  // same lookup games and movies use fills the name and offers photos of the
  // actual box. Loose retro hardware has no barcode — that stays typed in.
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
        title: cleanGameTitle(raw) || raw,
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
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, platformFilter, sort, tagFilter, tagsChanged]);

  // settings arrive after mount, so the default region is picked up on open
  const openForm = () => {
    setForm(blankForm());
    setArt([]);
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
        model_number: form.model_number.trim() || null,
        serial_number: form.serial_number.trim() || null,
        working: form.working,
        parent_id: form.parent_id ? Number(form.parent_id) : null,
        image_url: await api.localiseImage(form.image_url),
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
        <input
          type="search"
          placeholder="Search hardware…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button className="primary" onClick={openForm} title="Add hardware">
          <Icon id="plus" />
          Add
        </button>
      </div>

      <div className="chip-row">
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
        <TagFilter
          scope="hardware"
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
          <option value="platform">By system</option>
          <option value="added">Last added</option>
          <option value="oldest">First added</option>
        </select>
        <ViewToggle module="hardware" />
      </div>

      {/* no online catalogue knows retro hardware, so there is nothing to
          search and no reason to make you step through a search first */}
      <AddSheet open={showForm} title="Add hardware" onClose={closeForm}>
        <form className="add-form" onSubmit={submit}>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Name (SNES console, OEM controller…)"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <BarcodeScan onCode={onBarcode} />
          </div>
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
          </div>
          <div className="form-row">
            <select
              title="Working status"
              value={form.working}
              onChange={(e) => setForm({ ...form, working: e.target.value })}
            >
              {WORKING.map((w) => (
                <option key={w}>{w}</option>
              ))}
            </select>
            <select
              title="Part of (console)"
              value={form.parent_id}
              onChange={(e) => setForm({ ...form, parent_id: e.target.value })}
            >
              <option value="">Standalone…</option>
              {rows.map((h) => (
                <option key={h.id} value={h.id}>
                  goes with: {h.title}
                </option>
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

      <div className={`game-list ${tiles ? "as-tiles" : ""}`}>
        {rows.map((h) => (
          <HardwareRow
            key={h.id}
            hw={h}
            all={rows}
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

function HardwareRow({ hw, all, platforms, onChange, onReload , onTagsChanged}) {
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
  const parent = a.parent_id ? all.find((x) => x.id === a.parent_id) : null;
  const children = all.filter((x) => x.attrs.parent_id === hw.id);

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
      platform_id: a.platform_id ? String(a.platform_id) : "",
      region: a.region || "",
      model_number: a.model_number || "",
      serial_number: a.serial_number || "",
      working: a.working || "works",
      parent_id: a.parent_id ? String(a.parent_id) : "",
      image_url: hw.image_url,
      tags: hw.tags || [],
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
        title: entry.title.trim(),
        platform_id: entry.platform_id ? Number(entry.platform_id) : null,
        region: entry.region || null,
        model_number: entry.model_number.trim() || null,
        serial_number: entry.serial_number.trim() || null,
        working: entry.working,
        parent_id: entry.parent_id ? Number(entry.parent_id) : null,
        image_url: await api.localiseImage(entry.image_url),
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
          {a.model_number && <span>{a.model_number}</span>}
          {a.working && <span className={`hw-status ${a.working}`}>{a.working}</span>}
          {parent && <span>↳ {parent.title}</span>}
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
                  parent && `Goes with ${parent.title}`,
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
          {children.length > 0 && (
            <p className="game-summary">
              Connected gear: {children.map((c) => c.title).join(", ")}
            </p>
          )}
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
          </div>
          <div className="form-row">
            <select
              value={entry.working}
              onChange={(e) => setEntry({ ...entry, working: e.target.value })}
            >
              {WORKING.map((w) => (
                <option key={w}>{w}</option>
              ))}
            </select>
            <select
              value={entry.parent_id}
              onChange={(e) => setEntry({ ...entry, parent_id: e.target.value })}
            >
              <option value="">Standalone…</option>
              {all
                .filter((x) => x.id !== hw.id)
                .map((h) => (
                  <option key={h.id} value={h.id}>
                    goes with: {h.title}
                  </option>
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
