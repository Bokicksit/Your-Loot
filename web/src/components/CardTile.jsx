import { useState } from "react";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"];

// One card in the grid. Own/want actions update optimistically via onChange
// (parent swaps in the fresh status from the API response).
export default function CardTile({ card, onChange }) {
  const [busy, setBusy] = useState(false);
  const [condition, setCondition] = useState("NM");

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

  const addCopy = () => run(() => api.addOwned(card.id, { condition }));
  const removeCopy = () =>
    run(() => api.removeOwned(card.id, card.owned[card.owned.length - 1].id));
  const toggleWant = () =>
    run(() =>
      card.wanted ? api.removeWanted(card.id) : api.addWanted(card.id)
    );

  const ownedCount = card.owned.length;

  return (
    <div className={`tile ${ownedCount ? "tile-owned" : ""}`}>
      {ownedCount > 0 && <span className="owned-badge">×{ownedCount}</span>}
      {card.image_url ? (
        <img src={card.image_url} alt={card.title} loading="lazy" />
      ) : (
        <div className="placeholder" data-label={card.title} />
      )}
      <div className="tile-info">
        <strong>{card.title}</strong>
        <small>
          {card.attrs.set_name} #{card.attrs.card_number}
          {card.attrs.variant && card.attrs.variant !== "normal"
            ? ` · ${card.attrs.variant}`
            : ""}
        </small>
      </div>
      <div className="tile-actions">
        <button
          className={`want ${card.wanted ? "on" : ""}`}
          aria-pressed={!!card.wanted}
          onClick={toggleWant}
          disabled={busy}
          title={card.wanted ? "Remove from wanted" : "Add to wanted"}
        >
          <Icon id="star" />
        </button>
        <select value={condition} onChange={(e) => setCondition(e.target.value)}>
          {CONDITIONS.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        {ownedCount > 0 && (
          <button
            className="ghost icon danger"
            onClick={removeCopy}
            disabled={busy}
            title="Remove a copy"
          >
            <Icon id="minus" />
          </button>
        )}
        <button className="primary" onClick={addCopy} disabled={busy} title="Add owned copy">
          <Icon id="plus" />
        </button>
      </div>
    </div>
  );
}
