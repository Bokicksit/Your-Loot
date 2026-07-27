import { Fragment, useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

const LAYERS = [
  { key: "1", label: "Basic" },
  { key: "2", label: "Full Art" },
  { key: "3", label: "IR · SIR" },
];

// The binder mirror: one slot per national dex number, three layers each
// (Basic / Full Art EX / IR-SIR). A slot is settled when it has an IR/SIR
// or is marked "happy" (keeper card).
export default function PokedexPage() {
  const [entries, setEntries] = useState([]);
  const [filter, setFilter] = useState("all"); // all|missing|upgrade|done
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(null);

  useEffect(() => {
    api.pokedex().then((d) => setEntries(d.entries));
  }, []);

  const hasAny = (e) => e.layers["1"] || e.layers["2"] || e.layers["3"];
  const done = (e) => !!e.layers["3"] || (e.happy && hasAny(e));
  const status = (e) => (done(e) ? "done" : hasAny(e) ? "upgrade" : "missing");

  const toggleHappy = async (e) => {
    const next = !e.happy;
    await api.dexHappy(e.dex_no, next);
    setEntries((es) =>
      es.map((x) => (x.dex_no === e.dex_no ? { ...x, happy: next } : x))
    );
  };

  // pull this copy out of the binder (it stays in the collection)
  const removeFromBinder = async (c) => {
    if (!c.owned_id) return;
    await api.updateOwned(c.id, c.owned_id, { in_binder: false });
    api.pokedex().then((d) => setEntries(d.entries));
  };

  const q = query.trim().toLowerCase();
  const shown = entries.filter((e) => {
    if (filter !== "all" && status(e) !== filter) return false;
    if (!q) return true;
    if (q.startsWith("#")) return String(e.dex_no) === q.slice(1).replace(/^0+/, "");
    if (/^\d+$/.test(q)) return String(e.dex_no).startsWith(q);
    return (e.name || "").toLowerCase().includes(q);
  });

  const counts = {
    done: entries.filter((e) => status(e) === "done").length,
    upgrade: entries.filter((e) => status(e) === "upgrade").length,
  };

  const slotImage = (e) =>
    (e.layers["3"] || e.layers["2"] || e.layers["1"])?.image_url || null;

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Name or #025…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="count">
          {counts.done} / {entries.length || "…"}
        </span>
      </div>
      <div className="chip-row">
        {[
          ["all", "All"],
          ["missing", "Missing"],
          ["upgrade", `Needs upgrade (${counts.upgrade})`],
          ["done", "Done"],
        ].map(([k, label]) => (
          <button
            key={k}
            className={`chip ${filter === k ? "active" : ""}`}
            onClick={() => setFilter(k)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="dex-grid">
        {shown.map((e) => (
          <Fragment key={e.dex_no}>
            <button
              className={`dex-slot ${
                done(e) ? "owned" : hasAny(e) ? "partial" : "unowned"
              }`}
              aria-expanded={open === e.dex_no}
              onClick={() => setOpen(open === e.dex_no ? null : e.dex_no)}
            >
              <span className="dex-no">#{String(e.dex_no).padStart(4, "0")}</span>
              {slotImage(e) ? (
                <img src={slotImage(e)} alt={e.name || ""} loading="lazy" />
              ) : (
                <span className="placeholder" data-label="" />
              )}
              <span className="name">{e.name || "—"}</span>
              <span className="layer-pips">
                {LAYERS.map((l) => (
                  <span
                    key={l.key}
                    className={`pip ${e.layers[l.key] ? "filled" : ""}`}
                    title={l.label}
                  />
                ))}
                {e.happy && !e.layers["3"] && (
                  <span className="pip-happy" title="Happy with it">
                    <Icon id="check" />
                  </span>
                )}
              </span>
            </button>
            {open === e.dex_no && (
              <div className="dex-detail">
                <h3>
                  #{String(e.dex_no).padStart(4, "0")} {e.name || ""}
                  {e.copies > 0 && (
                    <span className="dex-no" style={{ marginLeft: "8px" }}>
                      ×{e.copies} copies
                    </span>
                  )}
                </h3>
                <ul>
                  {LAYERS.map((l) => {
                    const c = e.layers[l.key];
                    return (
                      <li key={l.key} className={c ? "" : "layer-empty"}>
                        <span className="layer-tag">{l.label}</span>
                        {c ? (
                          <>
                            {c.image_url && (
                              <img className="layer-thumb" src={c.image_url} alt="" loading="lazy" />
                            )}
                            <span className="game-text">
                              <strong>{c.title}</strong>
                              <small>
                                {c.set_name} #{c.card_number} · {c.rarity}
                              </small>
                            </span>
                            <button
                              className="ghost danger icon"
                              onClick={() => removeFromBinder(c)}
                              title="Remove from binder (stays in collection)"
                            >
                              <Icon id="x" />
                            </button>
                          </>
                        ) : (
                          <span className="game-text">
                            <small>empty — mark a copy "Binder" on the Cards tab</small>
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {!e.layers["3"] && hasAny(e) && (
                  <button
                    type="button"
                    className={`toggle ${e.happy ? "on" : ""}`}
                    onClick={() => toggleHappy(e)}
                  >
                    Happy with it — no IR/SIR needed
                  </button>
                )}
              </div>
            )}
          </Fragment>
        ))}
      </div>
      {shown.length === 0 && entries.length > 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="ball" /></span>
          <strong>No dex slots match</strong>
          <p>Adjust the filter or search.</p>
        </div>
      )}
    </div>
  );
}
