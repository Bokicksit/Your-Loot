import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

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
  const [platformFilter, setPlatformFilter] = useState("");
  const [sort, setSort] = useState("title");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.platforms().then(setPlatforms);
  }, []);

  const load = () => {
    const params = { is_hardware: true, sort, limit: 200 };
    if (search) params.search = search;
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
  }, [search, platformFilter, sort]);

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
        r.id === id ? { ...r, owned: status.owned, wanted: status.wanted } : r
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
        <button
          className={showForm ? "ghost icon" : "primary"}
          onClick={() => setShowForm(!showForm)}
          title={showForm ? "Close" : "Add hardware"}
        >
          <Icon id={showForm ? "x" : "plus"} />
          {!showForm && "Add"}
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
        </select>
      </div>

      {showForm && (
        <form className="add-form" onSubmit={submit}>
          <h2>Add hardware</h2>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Name (SNES console, OEM controller…)"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
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
      )}

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

      <div className="game-list">
        {rows.map((h) => (
          <HardwareRow
            key={h.id}
            hw={h}
            all={rows}
            platforms={platforms}
            onChange={patchRow}
            onReload={load}
          />
        ))}
      </div>
    </div>
  );
}

function HardwareRow({ hw, all, platforms, onChange, onReload }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // owned copy id
  const [editVals, setEditVals] = useState({ completeness: "loose", condition: "Good" });
  const [entryOpen, setEntryOpen] = useState(false);
  const [entry, setEntry] = useState({});
  const [infoOpen, setInfoOpen] = useState(false);

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
    setEntry({
      title: hw.title,
      platform_id: a.platform_id ? String(a.platform_id) : "",
      region: a.region || "",
      model_number: a.model_number || "",
      serial_number: a.serial_number || "",
      working: a.working || "works",
      parent_id: a.parent_id ? String(a.parent_id) : "",
    });
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
      });
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
    <div className={`game-row ${hw.owned.length ? "row-owned" : ""}`}>
      <span
        className="game-icon"
        style={{ cursor: "pointer" }}
        onClick={() => setInfoOpen(!infoOpen)}
      >
        <Icon id="console" />
      </span>
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
          </div>
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
