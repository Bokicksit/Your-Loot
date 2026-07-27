import { useState } from "react";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"];
const GRADERS = ["Raw", "PSA", "BGS", "CGC", "TAG", "ACE"];

// A card in the collection grid. Copies are chips ("PSA 9" / "NM") —
// tap a chip to edit condition + grading, + adds another copy.
export default function CardTile({ card, onChange }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // owned id being edited
  const [vals, setVals] = useState({ condition: "NM", grader: "Raw", grade: "" });

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
  const removeCopy = (ownedId) => run(() => api.removeOwned(card.id, ownedId));

  const openEdit = (o) => {
    setEditing(o.id);
    setVals({
      condition: o.condition || "NM",
      grader: o.grader || "Raw",
      grade: o.grade || "",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const graded = vals.grader !== "Raw";
      const status = await api.updateOwned(card.id, editing, {
        condition: vals.condition,
        grader: graded ? vals.grader : null,
        grade: graded && vals.grade ? vals.grade : null,
      });
      setEditing(null);
      return status;
    });

  const chipLabel = (o) =>
    o.grader ? `${o.grader} ${o.grade || "?"}` : o.condition || "set condition…";

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
        <small>
          {card.attrs.set_name} #{card.attrs.card_number}
          {card.attrs.set_total ? `/${card.attrs.set_total}` : ""}
        </small>
        <span className="copy-chips">
          {card.owned.map((o) => (
            <span
              key={o.id}
              className="chip copy"
              onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
              title="Edit this copy"
            >
              {chipLabel(o)}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeCopy(o.id);
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
      {editing !== null && (
        <div className="copy-edit stack">
          <select
            value={vals.condition}
            onChange={(e) => setVals({ ...vals, condition: e.target.value })}
          >
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <div className="form-row">
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
              disabled={vals.grader === "Raw"}
              value={vals.grade}
              onChange={(e) => setVals({ ...vals, grade: e.target.value })}
            />
          </div>
          <div className="form-row">
            <button className="primary icon" onClick={saveEdit} disabled={busy} title="Save">
              <Icon id="check" />
            </button>
            <button className="ghost icon" onClick={() => setEditing(null)} title="Cancel">
              <Icon id="x" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
