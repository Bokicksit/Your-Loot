import { Fragment, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { useSettings } from "../settings.jsx";

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
  // binder density lives in Settings so it applies on every device
  const { settings, save } = useSettings();
  const cols = settings?.dex_cols || 4;
  const navigate = useNavigate();

  const pickCols = (n) => save({ dex_cols: n });

  // jump straight to the Cards add flow, pre-searched for this Pokémon —
  // the usual next step when a slot is empty or wants an upgrade
  const findCards = (e, name) => {
    e.stopPropagation();
    if (name) navigate(`/cards?add=${encodeURIComponent(name)}`);
  };

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

  const [replacing, setReplacing] = useState(null); // dex_no showing candidates
  const [candidates, setCandidates] = useState(null); // null = still loading
  const [displaced, setDisplaced] = useState(null); // the card the swap evicted
  const [busy, setBusy] = useState(false);

  // Every other copy of this Pokémon you own — one entry per copy, since two
  // of the same card in different grades are genuinely different choices.
  const openReplace = async (e) => {
    if (replacing === e.dex_no) return setReplacing(null);
    setReplacing(e.dex_no);
    setCandidates(null);
    setDisplaced(null);
    try {
      const d = await api.cards({ dex_no: e.dex_no, include_binder: true, limit: 300 });
      setCandidates(
        d.items.flatMap((c) =>
          c.owned
            .filter((o) => o.id !== e.card?.owned_id)
            .map((o) => ({ card: c, owned: o }))
        )
      );
    } catch (err) {
      alert(err.message);
      setCandidates([]);
    }
  };

  // Flagging the new copy is the whole swap — the server turns the old one off,
  // one card per slot. It lands back in the collection, so the only open
  // question is whether you still want it.
  const swapIn = async (e, opt) => {
    if (busy) return;
    setBusy(true);
    try {
      await api.updateOwned(opt.card.id, opt.owned.id, { in_binder: true });
      setReplacing(null);
      setCandidates(null);
      setDisplaced(
        e.card
          ? { dex_no: e.dex_no, cardId: e.card.id, ownedId: e.card.owned_id, title: e.card.title }
          : null
      );
      load();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
  };

  const dropDisplaced = async () => {
    if (!displaced || busy) return;
    setBusy(true);
    try {
      await api.removeOwned(displaced.cardId, displaced.ownedId);
      setDisplaced(null);
      load();
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
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
            title="Filter by Pokédex-card rarity"
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
        <span className="col-picker" style={{ marginLeft: "auto" }}>
          {[3, 4, 5].map((n) => (
            <button
              key={n}
              className={`chip ${cols === n ? "active" : ""}`}
              title={`${n} per row`}
              onClick={() => pickCols(n)}
            >
              {n}
            </button>
          ))}
        </span>
      </div>

      <div
        className={`dex-grid cols-${cols}`}
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
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
              <span
                className={`name ${e.name ? "linked" : ""}`}
                title={e.name ? `Find ${e.name} cards` : undefined}
                onClick={(ev) => findCards(ev, e.name)}
              >
                {e.name || "—"}
              </span>
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
                  <button
                    type="button"
                    className="ghost"
                    style={{ marginLeft: "auto" }}
                    onClick={(ev) => findCards(ev, e.name)}
                  >
                    Find {e.name} cards
                  </button>
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
                        className="ghost"
                        onClick={() => openReplace(e)}
                        title="Swap in another copy you own"
                      >
                        <Icon id="pencil" />
                        {replacing === e.dex_no ? "Cancel" : "Replace"}
                      </button>
                      <button
                        type="button"
                        className="ghost danger icon"
                        style={{ marginLeft: "auto" }}
                        onClick={() => removeFromBinder(e)}
                        title="Remove from the Pokédex (stays in collection)"
                      >
                        <Icon id="x" />
                      </button>
                    </div>

                    {replacing === e.dex_no && (
                      <div className="replace-panel">
                        {candidates === null ? (
                          <span className="game-info-line">Looking…</span>
                        ) : candidates.length === 0 ? (
                          <>
                            <span className="game-info-line">
                              This is the only {e.name} you own.
                            </span>
                            <button
                              type="button"
                              className="ghost"
                              onClick={(ev) => findCards(ev, e.name)}
                            >
                              Find {e.name} cards
                            </button>
                          </>
                        ) : (
                          <>
                            <span className="game-info-line">
                              Swap in another {e.name} you own
                            </span>
                            <div className="grid pick-grid">
                              {candidates.map((opt) => (
                                <div
                                  key={opt.owned.id}
                                  className="tile pick"
                                  title="Put this one in the Pokédex"
                                  onClick={() => swapIn(e, opt)}
                                >
                                  {opt.card.image_url ? (
                                    <img src={opt.card.image_url} alt="" loading="lazy" />
                                  ) : (
                                    <div className="placeholder" data-label={opt.card.title} />
                                  )}
                                  <div className="tile-info">
                                    <strong>{opt.card.title}</strong>
                                    <small>
                                      {opt.card.attrs.set_abbr || opt.card.attrs.set_name} #
                                      {opt.card.attrs.card_number}
                                    </small>
                                    <small>
                                      {[
                                        opt.owned.variant,
                                        opt.owned.grader
                                          ? `${opt.owned.grader} ${opt.owned.grade || "?"}`
                                          : opt.owned.condition,
                                      ]
                                        .filter(Boolean)
                                        .join(" · ")}
                                    </small>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </>
                        )}
                      </div>
                    )}

                    {displaced?.dex_no === e.dex_no && (
                      <div className="replace-note">
                        <Icon id="info" />
                        <span>
                          <strong>{displaced.title}</strong> came out of the Pokédex and
                          is back in your collection.
                        </span>
                        <button
                          type="button"
                          className="ghost"
                          disabled={busy}
                          onClick={() => setDisplaced(null)}
                        >
                          Keep it
                        </button>
                        <button
                          type="button"
                          className="ghost danger"
                          disabled={busy}
                          onClick={dropDisplaced}
                          title="Delete that copy from your collection"
                        >
                          <Icon id="trash" />
                          Remove
                        </button>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="game-summary">
                    Empty slot — add a card on the Cards tab and mark it
                    "Pokédex".
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
