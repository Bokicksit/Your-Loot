import { Fragment, useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

const MODULE_ICONS = { cards: "card", games: "pad", movies: "disc" };

// Left-edge badge: system logo for games, media-format tag for movies,
// module icon otherwise.
function RowBadge({ row }) {
  const [logoOk, setLogoOk] = useState(true);
  if (row.module === "games" && row.badge && logoOk) {
    return (
      <span className="module-chip">
        <img
          className="plat-logo"
          src={`/platforms/${row.badge}.svg`}
          alt={row.badge}
          title={row.badge}
          onError={() => setLogoOk(false)}
        />
      </span>
    );
  }
  if (row.module === "movies" && row.badge) {
    return (
      <span className="module-chip media">
        <span className="plat-badge">{row.badge}</span>
      </span>
    );
  }
  return (
    <span className="module-chip">
      <Icon id={MODULE_ICONS[row.module] || "coin"} />
    </span>
  );
}
const FILTERS = [
  { key: "all", label: "All" },
  { key: "cards", label: "Cards", icon: "card" },
  { key: "games", label: "Games", icon: "pad" },
  { key: "movies", label: "Movies", icon: "disc" },
];
// condition vocabularies differ per module; completeness is games-only
const CONDITIONS = {
  cards: ["NM", "LP", "MP", "HP", "DMG"],
  games: ["Mint", "Good", "Fair", "Poor"],
  movies: ["Mint", "Good", "Fair", "Poor"],
};
const COMPLETENESS = ["loose", "CIB", "sealed"];

// The unified wanted list — every module, one view.
export default function WantedPage() {
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("all");
  const [facet, setFacet] = useState(""); // system (games) / genre (movies)
  const [acquiring, setAcquiring] = useState(null); // item_id being acquired
  const [acqVals, setAcqVals] = useState({});
  const [openInfo, setOpenInfo] = useState(null); // item_id with info expanded

  const load = () => api.wanted().then(setRows);
  useEffect(() => {
    load();
  }, []);

  const remove = async (itemId) => {
    await api.removeWanted(itemId);
    load();
  };

  // "Got it" opens a small editor so the copy lands with its real
  // condition/completeness instead of a blank record
  const startGotIt = (r) => {
    setAcquiring(r.item_id);
    // games & movies track completeness; cards are condition-only
    setAcqVals(
      r.module === "cards"
        ? { condition: CONDITIONS.cards[0] }
        : { completeness: "CIB", condition: "Good" }
    );
  };

  const confirmGotIt = async () => {
    await api.addOwned(acquiring, acqVals);
    await api.removeWanted(acquiring);
    setAcquiring(null);
    load();
  };

  // sold+completed eBay search for the item — best market-price proxy without
  // a paid pricing API. Title + first detail segment (set / platform).
  const ebayUrl = (r) => {
    // strip our "(1995)" year suffix — it needlessly narrows eBay matches
    const title = r.title.replace(/\s*\(\d{4}\)\s*$/, "");
    const q = [title, (r.detail || "").split("·")[0].trim()]
      .filter(Boolean)
      .join(" ");
    return `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(q)}&LH_Sold=1&LH_Complete=1`;
  };

  const moduleRows =
    filter === "all" ? rows : rows.filter((r) => r.module === filter);
  // sub-filter values present among the current module's wanted rows
  const facets =
    filter === "games" || filter === "movies"
      ? [...new Set(moduleRows.map((r) => r.facet).filter(Boolean))].sort()
      : [];
  const shown = facet
    ? moduleRows.filter((r) => r.facet === facet)
    : moduleRows;

  const pickFilter = (key) => {
    setFilter(key);
    setFacet("");
  };

  return (
    <div>
      <div className="chip-row">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`chip ${filter === f.key ? "active" : ""}`}
            onClick={() => pickFilter(f.key)}
          >
            {f.icon && <Icon id={f.icon} />}
            {f.label}
          </button>
        ))}
        <span className="count" style={{ marginLeft: "auto" }}>
          {shown.length}
        </span>
      </div>
      {facets.length > 0 && (
        <div className="chip-row">
          <button
            className={`chip ${facet === "" ? "active" : ""}`}
            onClick={() => setFacet("")}
          >
            {filter === "games" ? "All systems" : "All genres"}
          </button>
          {facets.map((f) => (
            <button
              key={f}
              className={`chip ${facet === f ? "active" : ""}`}
              onClick={() => setFacet(f)}
            >
              {f}
            </button>
          ))}
        </div>
      )}
      {shown.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="star" /></span>
          <strong>Nothing on the wishlist</strong>
          <p>Tap the star on any card, game, or movie and it lands here.</p>
        </div>
      )}
      <ul className="wanted-list">
        {shown.map((r) => (
          <Fragment key={r.item_id}>
            <li>
              <RowBadge row={r} />
              {r.image_url ? (
                <img src={r.image_url} alt="" loading="lazy" />
              ) : (
                <span className="placeholder" data-label="art" />
              )}
              <span
                className="game-text"
                style={{ cursor: "pointer" }}
                onClick={() =>
                  setOpenInfo(openInfo === r.item_id ? null : r.item_id)
                }
              >
                <strong>{r.title}</strong>
                <small>{r.detail}</small>
              </span>
              <a
                className="ghost icon"
                href={ebayUrl(r)}
                target="_blank"
                rel="noopener noreferrer"
                title="Check sold prices on eBay"
              >
                <Icon id="coin" />
              </a>
              <button
                className="primary icon"
                onClick={() =>
                  acquiring === r.item_id ? setAcquiring(null) : startGotIt(r)
                }
                title="Got it — move to library"
              >
                <Icon id="plus" />
              </button>
              <button
                className="ghost danger icon"
                onClick={() => remove(r.item_id)}
                title="Remove from wanted"
              >
                <Icon id="x" />
              </button>
            </li>
            {openInfo === r.item_id && (
              <li className="acquire-edit wanted-info">
                <div className="expand-card">
                  {r.image_url && (
                    <img className="expand-cover" src={r.image_url} alt="" loading="lazy" />
                  )}
                  <div className="expand-body">
                    <span className="expand-title">{r.title}</span>
                    {r.detail && <span className="expand-sub">{r.detail}</span>}
                    {r.info_line && (
                      <span className="game-info-line">{r.info_line}</span>
                    )}
                  </div>
                </div>
                {r.info_text && <p className="game-summary">{r.info_text}</p>}
              </li>
            )}
            {acquiring === r.item_id && (
              <li className="acquire-edit">
                <span className="acquire-label">Got it as:</span>
                {r.module !== "cards" && (
                  <select
                    value={acqVals.completeness}
                    onChange={(e) =>
                      setAcqVals({ ...acqVals, completeness: e.target.value })
                    }
                  >
                    {COMPLETENESS.map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                )}
                <select
                  value={acqVals.condition || ""}
                  onChange={(e) => setAcqVals({ ...acqVals, condition: e.target.value })}
                >
                  {(CONDITIONS[r.module] || CONDITIONS.games).map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
                <button className="primary icon" onClick={confirmGotIt} title="Confirm">
                  <Icon id="check" />
                </button>
                <button
                  className="ghost icon"
                  onClick={() => setAcquiring(null)}
                  title="Cancel"
                >
                  <Icon id="x" />
                </button>
              </li>
            )}
          </Fragment>
        ))}
      </ul>
    </div>
  );
}
