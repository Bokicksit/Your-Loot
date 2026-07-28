import { useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"];
const GRADERS = ["Raw", "PSA", "BGS", "CGC", "TAG", "ACE"];

// A card in the collection grid. Copies are chips ("PSA 9" / "NM") —
// tap a chip to edit in a modal (tiles are too narrow for an inline form),
// + adds another copy. Graded chips are jade, binder chips carry a pokéball.
export default function CardTile({ card, onChange }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // owned id being edited
  const [vals, setVals] = useState({
    condition: "NM",
    grader: "Raw",
    grade: "",
    in_binder: false,
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
      });
      setEditing(null);
      return status;
    });

  const chipLabel = (o) =>
    o.grader ? `${o.grader} ${o.grade || "?"}` : o.condition || "set condition…";

  const setLine = `${card.attrs.set_name} #${card.attrs.card_number}${
    card.attrs.set_total ? `/${card.attrs.set_total}` : ""
  }`;

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
    <div className={`tile ${card.owned.length ? "tile-owned" : ""}`}>
      {card.owned.length > 0 && <span className="owned-badge">×{card.owned.length}</span>}
      {card.image_url ? (
        <img src={card.image_url} alt={card.title} loading="lazy" />
      ) : (
        <div className="placeholder" data-label={card.title} />
      )}
      <div className="tile-info">
        <strong>{card.title}</strong>
        <small>{setLine}</small>
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
  );
}
