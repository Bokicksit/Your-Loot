import { Fragment, useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import {
  COMIC_GRADES,
  DEFAULT_VINYL_GRADE,
  GAME_COMPLETENESS,
  GAME_PARTS_ONLY,
  LEGO_COMPLETENESS,
  LEGO_CONDITION,
  LEGO_PARTS_ONLY,
  VINYL_GRADES,
} from "../vocab.js";
import { useEnabledModules } from "../settings.jsx";

const MODULE_ICONS = {
  cards: "card", games: "pad", hardware: "console", movies: "disc", books: "book",
  records: "vinyl", lego: "brick", comics: "comic",
};

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
// filter chips are built from the collections you actually have enabled
// Each collection grades on its own scale — a book is "Near Fine", never "NM".
// An option is either a plain value or a [value, label] pair.
const CONDITIONS = {
  cards: ["NM", "LP", "MP", "HP", "DMG"],
  games: ["Mint", "Good", "Fair", "Poor"],
  hardware: ["Mint", "Good", "Fair", "Poor"],
  movies: ["Mint", "Good", "Fair", "Poor"],
  books: ["Fine", "Near Fine", "Very Good", "Good", "Fair", "Poor"],
  records: VINYL_GRADES,
  lego: LEGO_CONDITION,
  comics: COMIC_GRADES,
};
// most acquisitions aren't mint, so default to the sensible middle of each scale
const DEFAULT_CONDITION = {
  cards: "NM", games: "Good", hardware: "Good", movies: "Good",
  books: "Very Good", records: DEFAULT_VINYL_GRADE, lego: "used", comics: "VF",
};
const BOX = ["loose", "CIB", "sealed"];
// The optional second per-copy field, and which column it writes to. Cards
// have none; records grade the sleeve separately rather than tracking a box.
const SECOND_FIELD = {
  games: { key: "completeness", options: GAME_COMPLETENESS, def: "CIB" },
  hardware: { key: "completeness", options: BOX, def: "CIB" },
  movies: { key: "completeness", options: BOX, def: "CIB" },
  books: {
    key: "completeness",
    options: ["With jacket", "No jacket", "Ex-library", "Signed"],
    def: "With jacket",
  },
  records: {
    key: "sleeve_condition",
    options: VINYL_GRADES,
    def: DEFAULT_VINYL_GRADE,
  },
  lego: { key: "completeness", options: LEGO_COMPLETENESS, def: "complete+box" },
  // comics have no second field: a slab's grade goes on grader/grade, edited
  // on the comics page, exactly like a graded card
};

// Records grade two things on the same scale, so the two selects have to say
// which is which — everywhere else the vocabularies already differ.
const GRADE_PREFIX = { records: ["Media", "Sleeve"] };

const pair = (o) => (Array.isArray(o) ? o : [o, o]);
const label = (text, prefix) => (prefix ? `${prefix}: ${text}` : text);

// The unified wanted list — every module, one view.
export default function WantedPage() {
  const enabled = useEnabledModules();
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
    const second = SECOND_FIELD[r.module];
    setAcqVals({
      condition: DEFAULT_CONDITION[r.module] || "Good",
      ...(second ? { [second.key]: second.def } : {}),
    });
  };

  // Buying the case, the manual or an empty LEGO box isn't getting the thing —
  // record the piece you found, but keep hunting what you're actually after.
  const keepsHunting = (vals) =>
    GAME_PARTS_ONLY.has(vals.completeness) || LEGO_PARTS_ONLY.has(vals.completeness);

  const confirmGotIt = async () => {
    await api.addOwned(acquiring, acqVals);
    if (!keepsHunting(acqVals)) await api.removeWanted(acquiring);
    setAcquiring(null);
    load();
  };

  // sold+completed eBay search for the item — best market-price proxy without
  // a paid pricing API.
  const ebayUrl = (r) => {
    // strip our "(1995)" year suffix — it needlessly narrows eBay matches
    const title = r.title.replace(/\s*\(\d{4}\)\s*$/, "").trim();
    const said = (s) => title.toLowerCase().includes(s.toLowerCase());
    const parts = (r.detail || "").split("·").map((s) => s.trim()).filter(Boolean);

    // The detail line leads with whatever narrows that collection — platform,
    // artist, author, set number. Drop it when the title already says it
    // rather than substituting the next segment, which is usually a region
    // code no seller writes in a listing.
    const lead = parts[0] && !said(parts[0]) ? parts[0] : null;

    // Comics are the one collection whose title is assembled from the detail
    // ("Amazing Spider-Man #300"), so the lead is always a duplicate. What
    // actually separates two listings of one issue is the variant cover.
    const variant =
      r.module === "comics"
        ? parts.slice(1).filter((p) => !p.startsWith("#") && !said(p)).pop()
        : null;

    const q = [title, lead, variant].filter(Boolean).join(" ");
    return `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(q)}&LH_Sold=1&LH_Complete=1`;
  };

  // items from collections you've turned off stay in the database but drop
  // out of the hunt list, matching the rest of the app
  const enabledKeys = enabled.map((m) => m.key);
  const visible = rows.filter((r) => enabledKeys.includes(r.module));
  const moduleRows =
    filter === "all" ? visible : visible.filter((r) => r.module === filter);
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
        {[{ key: "all", label: "All" }, ...enabled].map((f) => (
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
                <select
                  value={acqVals.condition || ""}
                  onChange={(e) => setAcqVals({ ...acqVals, condition: e.target.value })}
                >
                  {(CONDITIONS[r.module] || CONDITIONS.games).map(pair).map(([v, l]) => (
                    <option key={v} value={v}>
                      {label(l, (GRADE_PREFIX[r.module] || [])[0])}
                    </option>
                  ))}
                </select>
                {SECOND_FIELD[r.module] && (
                  <select
                    value={acqVals[SECOND_FIELD[r.module].key] || ""}
                    onChange={(e) =>
                      setAcqVals({
                        ...acqVals,
                        [SECOND_FIELD[r.module].key]: e.target.value,
                      })
                    }
                  >
                    {SECOND_FIELD[r.module].options.map(pair).map(([v, l]) => (
                      <option key={v} value={v}>
                        {label(l, (GRADE_PREFIX[r.module] || [])[1])}
                      </option>
                    ))}
                  </select>
                )}
                {keepsHunting(acqVals) && (
                  <span className="acquire-note">
                    Saved as a spare — “{r.title}” stays on your wanted list.
                  </span>
                )}
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
