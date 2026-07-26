import { Fragment, useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

const MODULE_ICONS = { cards: "card", games: "pad", movies: "disc" };
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
  const [acquiring, setAcquiring] = useState(null); // item_id being acquired
  const [acqVals, setAcqVals] = useState({});

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

  const shown = filter === "all" ? rows : rows.filter((r) => r.module === filter);

  return (
    <div>
      <div className="chip-row">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`chip ${filter === f.key ? "active" : ""}`}
            onClick={() => setFilter(f.key)}
          >
            {f.icon && <Icon id={f.icon} />}
            {f.label}
          </button>
        ))}
        <span className="count" style={{ marginLeft: "auto" }}>
          {shown.length}
        </span>
      </div>
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
              <span className="module-chip">
                <Icon id={MODULE_ICONS[r.module] || "coin"} />
              </span>
              {r.image_url ? (
                <img src={r.image_url} alt="" loading="lazy" />
              ) : (
                <span className="placeholder" data-label="art" />
              )}
              <span className="game-text">
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
