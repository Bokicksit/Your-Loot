import { Fragment, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import useDismiss from "../useDismiss.js";
import { Icon } from "../components/Icons.jsx";
import {
  BinderPages,
  PageBox,
  pageIndex,
  usePageTracker,
} from "../components/BinderGrid.jsx";
import EbayLink from "../components/EbayLink.jsx";
import BinderShape from "../components/BinderShape.jsx";
import { useSettings } from "../settings.jsx";

// One card per Pokémon — the binder mirror. A slot's occupant is either the
// desired card ("the one") or a placeholder awaiting an upgrade; some basics
// stay forever by choice, and that's what the final flag records.
const abbrevRarity = (r) =>
  r ? r.split(/\s+/).map((w) => w[0]).join("").toUpperCase() : "";

export default function PokedexPage() {
  const [entries, setEntries] = useState([]);
  // The dex binder's own shape, and its id so this page can save changes to
  // it. This is the only page that draws the Pokédex — the binder route sends
  // you here — so the shape is set here too.
  const [shape, setShape] = useState({ rows: 3, cols: 3, double_page: false });
  const [shapeOpen, setShapeOpen] = useState(false);
  const [shapeBusy, setShapeBusy] = useState(false);
  const [shapeError, setShapeError] = useState(null);
  const [filter, setFilter] = useState("all"); // all|missing|upgrade|final
  const [rarityFilter, setRarityFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  // the status chips show their own state in the rail, so the badge counts
  // only what the button is hiding
  const activeFilters = [rarityFilter].filter(Boolean).length;
  // plain state here, not stored preferences — nothing to batch
  const clearFilters = () => setRarityFilter("");

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(null);
  // the slot and its detail panel are siblings, and which is open lives on
  // the page rather than in a row, so they carry their dex number instead
  useDismiss(
    open !== null,
    () => setOpen(null),
    (t) => t.closest?.("[data-slot]")?.dataset.slot === String(open),
  );
  const { settings, save } = useSettings();
  const navigate = useNavigate();


  // Jump straight to the Cards add flow, pre-searched for this Pokémon — the
  // usual next step when a slot is empty or wants an upgrade. The dex number
  // travels with it so the way back lands on the slot you left rather than at
  // the top of a thousand of them.
  const findCards = (e, name, dexNo) => {
    e.stopPropagation();
    if (name) {
      const back = dexNo ? `&from=${dexNo}` : "";
      navigate(`/cards?add=${encodeURIComponent(name)}${back}`);
    }
  };

  const load = () =>
    api.pokedex().then((d) => {
      setEntries(d.entries);
      if (d.binder) setShape(d.binder);
    });
  useEffect(() => {
    load();
  }, []);

  // Rebuilt whenever the pages are redrawn — a filter, a search, a new shape.
  const [pageNo, goToPage] = usePageTracker(
    `${entries.length}:${filter}:${rarityFilter}:${query}:${shape.rows}x${shape.cols}`
  );

  /** Come back to the slot you left.
   *
   *  Waits for the slots to exist — the binder is a thousand of them and the
   *  page renders before they arrive, so scrolling on mount would scroll an
   *  empty page. Centred rather than aligned to the top, because the slot you
   *  were looking at was in the middle of the screen when you left it.
   */
  const [params, setParams] = useSearchParams();
  const at = params.get("at");
  useEffect(() => {
    if (!at || !entries.length) return;
    // Keep trying until it lands. Two things go wrong with a single attempt:
    // a thousand slots take more than a frame to commit, so the element is
    // often not there yet; and the grid settles its column count afterwards,
    // which moves the row out from under a scroll that already happened — the
    // first version missed by thirty slots.
    //
    // "Landed" means the slot is on screen, not that it is centred: a slot is
    // taller than the viewport on a phone, so asking for its middle to sit at
    // the viewport's middle is a test that can never pass.
    let tries = 0;
    const timer = setInterval(() => {
      const slot = document.querySelector(`[data-slot="${CSS.escape(at)}"]`);
      if (slot) {
        slot.scrollIntoView({ block: "center", behavior: "auto" });
        const r = slot.getBoundingClientRect();
        // A viewport of zero is not a viewport — nothing can intersect it, so
        // the test would never pass and the poll would spin until it expired.
        const h = Math.max(window.innerHeight || 0, 1);
        if (r.bottom > 0 && r.top < h) {
          clearInterval(timer);
          setParams({}, { replace: true });
          return;
        }
      }
      // about a second and a half, then give up and leave the page where it
      // is — arriving at the top is a disappointment, not a fault
      if (++tries > 30) clearInterval(timer);
    }, 50);
    return () => clearInterval(timer);
  }, [at, entries.length]);

  /** The dex binder is a binder like any other, so this is the same PATCH the
   *  binder page sends — the Pokédex just has nowhere else to send it from. */
  const saveShape = async (ev) => {
    ev.preventDefault();
    if (!shape.id) return setShapeOpen(false);
    setShapeBusy(true);
    setShapeError(null);
    try {
      await api.editBinder(shape.id, {
        rows: shape.rows,
        cols: shape.cols,
        double_page: shape.double_page,
        color: shape.color || "",
      });
      setShapeOpen(false);
    } catch (e) {
      setShapeError(e.message);
    } finally {
      setShapeBusy(false);
    }
  };

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

  // Looking at matches rather than at the binder. Frames and page numbers are
  // for the binder; a handful of Pokémon from all over it is a result list,
  // and numbering that 1, 2, 3 said "page 1" for a card sitting on page 15.
  const searching = filter !== "all" || !!rarityFilter || q !== "";

  // Where each slot really lives, counted down the whole Pokédex.
  const homePage = pageIndex(entries, shape, (e) => e.dex_no);
  const listed = searching
    ? shown.map((e) => ({ ...e, page: homePage.get(e.dex_no) }))
    : shown;

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
      </div>

      {/* Its own row. The chips above are the question the page answers and
          are read constantly; these two are settings for how it is drawn,
          and sharing a line made both harder to find. */}
      <div className="chip-row">
        <button
          type="button"
          className={`chip ${activeFilters ? "active" : ""}`}
          onClick={() => setFiltersOpen(!filtersOpen)}
          aria-expanded={filtersOpen}
          title="Filters"
        >
          <Icon id="sliders" />
          Filters
          {activeFilters > 0 && <span className="chip-n">{activeFilters}</span>}
        </button>
        <PageBox
          page={pageNo}
          total={Math.ceil(
            entries.length / Math.max(1, (shape.rows || 3) * (shape.cols || 3))
          )}
          onGo={goToPage}
        />
        <span className="rail-spacer" />
        {/* The tile slider was here. The Pokédex is a binder, and how wide it
            is drawn is a fact about that binder — set here, because this is
            the Pokédex's page and there is no other. */}
        <button
          type="button"
          className={`chip ${shapeOpen ? "active" : ""}`}
          onClick={() => setShapeOpen(!shapeOpen)}
          aria-expanded={shapeOpen}
          title="Pockets to a page, and the cover"
        >
          <Icon id="grid" />
          {shape.cols}×{shape.rows}
          {shape.double_page ? " · spread" : ""}
        </button>
      </div>
      {shapeOpen && (
        <form className="filter-sheet" onSubmit={saveShape}>
          <BinderShape value={shape} onChange={setShape} />
          {shapeError && <p className="error">{shapeError}</p>}
          <button type="submit" className="primary" disabled={shapeBusy}>
            <Icon id="check" />
            {shapeBusy ? "…" : "Save"}
          </button>
          <button type="button" className="ghost" onClick={() => setShapeOpen(false)}>
            Cancel
          </button>
        </form>
      )}
      {filtersOpen && (
        <div className="filter-sheet">
          <label>
            <span>Rarity</span>
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
          </label>
          {activeFilters > 0 && (
            <button type="button" className="ghost" onClick={clearFilters}>
              Clear {activeFilters === 1 ? "filter" : "all filters"}
            </button>
          )}
        </div>
      )}

      <BinderPages binder={shape} entries={listed} flat={searching}>
        {(e) => (
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
              data-slot={e.dex_no}
              onClick={() => setOpen(open === e.dex_no ? null : e.dex_no)}
            >
              <span className="dex-no">#{String(e.dex_no).padStart(4, "0")}</span>
              {/* only while searching — on the binder proper you can see
                  which page you are on */}
              {e.page ? <span className="slot-page">p.{e.page}</span> : null}
              {e.card?.image_url ? (
                <img src={e.card.image_url} alt={e.name || ""} loading="lazy" />
              ) : (
                <span className="placeholder" data-label="" />
              )}
              <span
                className={`name ${e.name ? "linked" : ""}`}
                title={e.name ? `Find ${e.name} cards` : undefined}
                onClick={(ev) => findCards(ev, e.name, e.dex_no)}
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
              <div className="dex-detail" data-slot={e.dex_no}>
                <h3>
                  #{String(e.dex_no).padStart(4, "0")} {e.name || ""}
                  <button
                    type="button"
                    className="ghost"
                    style={{ marginLeft: "auto" }}
                    onClick={(ev) => findCards(ev, e.name, e.dex_no)}
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
                      {/* what this copy is worth, from the same sold-listings
                          search the Cards page uses */}
                      <EbayLink
                        title={e.card.title}
                        terms={[
                          `${e.card.card_number}${
                            e.card.set_total ? `/${e.card.set_total}` : ""
                          }`,
                          e.card.set_name,
                        ]}
                      />
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
                              onClick={(ev) => findCards(ev, e.name, e.dex_no)}
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
        )}
      </BinderPages>
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
