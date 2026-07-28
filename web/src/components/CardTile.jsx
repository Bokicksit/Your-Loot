import { useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";
import ImagePicker from "./ImagePicker.jsx";
import RarityMark from "./RarityMark.jsx";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"];
const GRADERS = ["Raw", "PSA", "BGS", "CGC", "TAG", "ACE"];
const VARIANTS = ["Non-Holo", "Reverse Holo", "Holo"];
const VARIANT_SHORT = { "Reverse Holo": "RH", Holo: "Holo" };

// A card in the collection grid. Copies are chips ("PSA 9" / "NM") —
// tap a chip to edit in a modal (tiles are too narrow for an inline form),
// + adds another copy. Graded chips are jade, binder chips carry a pokéball.
export default function CardTile({ card, onChange, onReload }) {
  const [busy, setBusy] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false); // full-width expansion
  const [editing, setEditing] = useState(null); // owned id being edited
  const [vals, setVals] = useState({
    condition: "NM",
    grader: "Raw",
    grade: "",
    in_binder: false,
    variant: "Non-Holo",
    stamp: "",
  });

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      const status = await fn();
      onChange(card.id, status);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const addCopy = () => run(() => api.addOwned(card.id, { condition: "NM" }));
  const removeCopy = (o) => {
    const last = card.owned.length === 1;
    if (
      !confirm(
        `Remove ${card.title} (${chipLabel(o)})?` +
          (last ? " This is your last copy — it leaves the collection." : "")
      )
    )
      return;
    run(() => api.removeOwned(card.id, o.id));
  };

  const openEdit = (o) => {
    setEditing(o.id);
    setVals({
      condition: o.condition || "NM",
      grader: o.grader || "Raw",
      grade: o.grade || "",
      in_binder: o.in_binder,
      variant: o.variant || "Non-Holo",
      stamp: o.stamp || "",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const graded = vals.grader !== "Raw";
      const status = await api.updateOwned(card.id, editing, {
        condition: vals.condition,
        grader: graded ? vals.grader : null,
        grade: graded && vals.grade ? vals.grade : null,
        in_binder: vals.in_binder && !!card.attrs.national_dex_no,
        variant: vals.variant === "Non-Holo" ? null : vals.variant,
        stamp: vals.stamp.trim() || null,
      });
      setEditing(null);
      return status;
    });

  const chipLabel = (o) =>
    [
      VARIANT_SHORT[o.variant],
      o.grader ? `${o.grader} ${o.grade || "?"}` : o.condition,
      o.stamp && "stamped",
    ]
      .filter(Boolean)
      .join(" · ") || "set condition…";

  const a = card.attrs;
  // tile stays terse: the printed set code, full name lives in the expansion
  const shortSet = a.set_abbr || a.set_name;
  const numLine = `#${a.card_number}${a.set_total ? `/${a.set_total}` : ""}`;
  const setLine = `${a.set_name} ${numLine}`;

  const editorModal = (
    <div className="modal-scrim" onClick={() => setEditing(null)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Edit copy</h2>
        <p>
          {card.title} · {setLine}
        </p>
        <div className="form-row" style={{ width: "100%" }}>
          <select
            value={vals.condition}
            onChange={(e) => setVals({ ...vals, condition: e.target.value })}
          >
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <select
            value={vals.grader}
            onChange={(e) => setVals({ ...vals, grader: e.target.value })}
          >
            {GRADERS.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
          <input
            type="text"
            inputMode="decimal"
            placeholder="9.5"
            style={{ maxWidth: "80px" }}
            disabled={vals.grader === "Raw"}
            value={vals.grade}
            onChange={(e) => setVals({ ...vals, grade: e.target.value })}
          />
        </div>
        <div className="form-row" style={{ width: "100%" }}>
          <select
            value={vals.variant}
            onChange={(e) => setVals({ ...vals, variant: e.target.value })}
          >
            {VARIANTS.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <input
            type="text"
            className="grow"
            placeholder="Stamp (Mega Evolution…)"
            value={vals.stamp}
            onChange={(e) => setVals({ ...vals, stamp: e.target.value })}
          />
        </div>
        {card.attrs.national_dex_no && (
          <button
            type="button"
            className={`toggle ${vals.in_binder ? "on" : ""}`}
            onClick={() => setVals({ ...vals, in_binder: !vals.in_binder })}
          >
            In the Pokédex binder
          </button>
        )}
        <div className="form-row" style={{ width: "100%" }}>
          <button
            className="primary"
            style={{ flex: 1 }}
            onClick={saveEdit}
            disabled={busy}
          >
            <Icon id="check" />
            Save
          </button>
          <button className="ghost" onClick={() => setEditing(null)}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
    <div className={`tile ${card.owned.length ? "tile-owned" : ""}`}>
      {card.owned.length > 0 && <span className="owned-badge">×{card.owned.length}</span>}
      {card.image_url ? (
        <img
          src={card.image_url}
          alt={card.title}
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={() => setDetailOpen(!detailOpen)}
        />
      ) : (
        <div
          className="placeholder"
          data-label={card.title}
          style={{ cursor: "pointer" }}
          onClick={() => setDetailOpen(!detailOpen)}
        />
      )}
      <div className="tile-info">
        <strong style={{ cursor: "pointer" }} onClick={() => setDetailOpen(!detailOpen)}>
          {card.title}
        </strong>
        <small style={{ cursor: "pointer" }} onClick={() => setDetailOpen(!detailOpen)}>
          <RarityMark rarity={a.rarity} />
          <span className="set-abbr">{shortSet}</span> {numLine}
        </small>
        <span className="copy-chips">
          {card.owned.map((o) => (
            <span
              key={o.id}
              className={`chip copy ${o.grader ? "graded" : ""}`}
              onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
              title="Edit this copy"
            >
              {o.in_binder && <Icon id="ball" />}
              {chipLabel(o)}
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
          <button
            className="chip copy add"
            onClick={addCopy}
            disabled={busy}
            title="Add another copy"
          >
            <Icon id="plus" />
          </button>
        </span>
      </div>
      {editing !== null && createPortal(editorModal, document.body)}
    </div>
    {detailOpen && (
      <div className="dex-detail card-detail">
        <div className="expand-card">
          {card.image_url && (
            <img className="expand-cover" src={card.image_url} alt="" loading="lazy" />
          )}
          <div className="expand-body">
            <span className="expand-title">{card.title}</span>
            <span className="expand-sub">
              {a.set_name}
              {a.set_abbr ? ` (${a.set_abbr})` : ""}
              {a.set_year ? ` · ${a.set_year}` : ""}
            </span>
            <span className="game-info-line">
              <RarityMark rarity={a.rarity} /> {a.rarity || "—"} · Card {numLine}
              {a.national_dex_no ? ` · Dex #${a.national_dex_no}` : ""}
            </span>
          </div>
        </div>
        <ul>
          {card.owned.map((o) => (
            <li key={o.id}>
              <span className="layer-tag">{o.in_binder ? "Binder" : "Box"}</span>
              <span className="game-text">
                <strong>{chipLabel(o)}</strong>
                {o.stamp && <small>{o.stamp} stamp</small>}
              </span>
              <button className="ghost icon" onClick={() => openEdit(o)} title="Edit copy">
                <Icon id="pencil" />
              </button>
            </li>
          ))}
        </ul>
        {card.source === "manual" && (
          <div className="form-row wrap">
            <ImagePicker
              value={card.image_url}
              label="Add photo"
              onChange={async (url) => {
                try {
                  await api.updateCard(card.id, { image_url: url });
                  onReload?.();
                } catch (e) {
                  alert(e.message);
                }
              }}
            />
            <button
              className="ghost danger icon"
              style={{ marginLeft: "auto" }}
              title="Delete this manual card entry"
              onClick={async () => {
                if (!confirm(`Delete the manual card entry "${card.title}"?`)) return;
                try {
                  await api.deleteCard(card.id);
                  onReload?.();
                } catch (e) {
                  alert(e.message);
                }
              }}
            >
              <Icon id="trash" />
            </button>
          </div>
        )}
      </div>
    )}
    </>
  );
}
