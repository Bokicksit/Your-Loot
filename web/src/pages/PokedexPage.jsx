import { Fragment, useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

// One card per Pokémon — the binder mirror. A slot's occupant is either the
// desired card ("the one") or a placeholder awaiting an upgrade; some basics
// stay forever by choice, and that's what the final flag records.
const abbrevRarity = (r) =>
  r ? r.split(/\s+/).map((w) => w[0]).join("").toUpperCase() : "";

export default function PokedexPage() {
  const [entries, setEntries] = useState([]);
  const [filter, setFilter] = useState("all"); // all|missing|upgrade|final
  const [rarityFilter, setRarityFilter] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(null);

  const load = () => api.pokedex().then((d) => setEntries(d.entries));
  useEffect(() => {
    load();
  }, []);

  const status = (e) => (e.card ? (e.final ? "final" : "upgrade") : "missing");

  const toggleFinal = async (e) => {
    const next = !e.final;
    await api.dexHappy(e.dex_no, next);
    setEntries((es) =>
      es.map((x) => (x.dex_no === e.dex_no ? { ...x, final: next } : x))
    );
  };

  // pull the occupant out of the binder (the copy stays in the collection)
  const removeFromBinder = async (e) => {
    if (!e.card?.owned_id) return;
    await api.updateOwned(e.card.id, e.card.owned_id, { in_binder: false });
    await api.dexHappy(e.dex_no, false);
    load();
  };

  const q = query.trim().toLowerCase();
  const shown = entries.filter((e) => {
    if (filter !== "all" && status(e) !== filter) return false;
    if (rarityFilter && e.card?.rarity !== rarityFilter) return false;
    if (!q) return true;
    if (q.startsWith("#")) return String(e.dex_no) === q.slice(1).replace(/^0+/, "");
    if (/^\d+$/.test(q)) return String(e.dex_no).startsWith(q);
    return (e.name || "").toLowerCase().includes(q);
  });

  const counts = {
    missing: entries.filter((e) => status(e) === "missing").length,
    upgrade: entries.filter((e) => status(e) === "upgrade").length,
    final: entries.filter((e) => status(e) === "final").length,
  };

  // rarities actually present in the binder, with counts
  const rarities = Object.entries(
    entries.reduce((acc, e) => {
      if (e.card?.rarity) acc[e.card.rarity] = (acc[e.card.rarity] || 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => a[0].localeCompare(b[0]));

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
          {counts.final} / {entries.length || "…"} final
        </span>
      </div>
      <div className="chip-row">
        {[
          ["all", "All"],
          ["missing", `Missing (${counts.missing})`],
          ["upgrade", `Needs upgrade (${counts.upgrade})`],
          ["final", `The one (${counts.final})`],
        ].map(([k, label]) => (
          <button
            key={k}
            className={`chip ${filter === k ? "active" : ""}`}
            onClick={() => setFilter(k)}
          >
            {label}
          </button>
        ))}
        {rarities.length > 0 && (
          <select
            className="chip-select"
            title="Filter by binder-card rarity"
            value={rarityFilter}
            onChange={(e) => setRarityFilter(e.target.value)}
          >
            <option value="">All rarities</option>
            {rarities.map(([r, n]) => (
              <option key={r} value={r}>
                {r} ({n})
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="dex-grid">
        {shown.map((e) => (
          <Fragment key={e.dex_no}>
            <button
              className={`dex-slot ${
                status(e) === "final"
                  ? "owned"
                  : status(e) === "upgrade"
                  ? "partial"
                  : "unowned"
              }`}
              aria-expanded={open === e.dex_no}
              onClick={() => setOpen(open === e.dex_no ? null : e.dex_no)}
            >
              <span className="dex-no">#{String(e.dex_no).padStart(4, "0")}</span>
              {e.card?.image_url ? (
                <img src={e.card.image_url} alt={e.name || ""} loading="lazy" />
              ) : (
                <span className="placeholder" data-label="" />
              )}
              <span className="name">{e.name || "—"}</span>
              <span className="layer-pips">
                {e.card?.set_abbr && (
                  <span className="set-abbr" title={e.card.set_name}>
                    {e.card.set_abbr}
                  </span>
                )}
                {e.card && (
                  <span className="rarity-tag" title={e.card.rarity}>
                    {abbrevRarity(e.card.rarity)}
                  </span>
                )}
                {e.final && e.card && (
                  <span className="pip-happy" title="The one">
                    <Icon id="check" />
                  </span>
                )}
              </span>
            </button>
            {open === e.dex_no && (
              <div className="dex-detail">
                <h3>
                  #{String(e.dex_no).padStart(4, "0")} {e.name || ""}
                </h3>
                {e.card ? (
                  <>
                    <div className="expand-card">
                      {e.card.image_url && (
                        <img
                          className="expand-cover"
                          src={e.card.image_url}
                          alt=""
                          loading="lazy"
                        />
                      )}
                      <div className="expand-body">
                        <span className="expand-title">{e.card.title}</span>
                        <span className="expand-sub">
                          {e.card.set_name}
                          {e.card.set_abbr ? ` (${e.card.set_abbr})` : ""}
                          {e.card.set_year ? ` · ${e.card.set_year}` : ""}
                        </span>
                        <span className="game-info-line">
                          {e.card.rarity} · Card #{e.card.card_number}
                          {e.card.set_total ? `/${e.card.set_total}` : ""}
                        </span>
                        <span className="expand-sub">
                          {[
                            e.card.variant,
                            e.card.grader
                              ? `${e.card.grader} ${e.card.grade || "?"}`
                              : e.card.condition,
                            e.card.stamp && `${e.card.stamp} stamp`,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </div>
                    </div>
                    <div className="form-row">
                      <button
                        type="button"
                        className={`toggle ${e.final ? "on" : ""}`}
                        onClick={() => toggleFinal(e)}
                      >
                        {e.final ? "The one ✓" : "Will upgrade"}
                      </button>
                      <button
                        type="button"
                        className="ghost danger icon"
                        style={{ marginLeft: "auto" }}
                        onClick={() => removeFromBinder(e)}
                        title="Remove from binder (stays in collection)"
                      >
                        <Icon id="x" />
                      </button>
                    </div>
                  </>
                ) : (
                  <p className="game-summary">
                    Empty slot — add a card on the Cards tab and mark it
                    "Binder".
                  </p>
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
