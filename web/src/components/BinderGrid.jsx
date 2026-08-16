import { NavLink } from "react-router-dom";

/** The row of chips that says which shelf of cards you are looking at.
 *
 *  Routes rather than local state, because a binder is a thing you send
 *  somebody a link to, and because the Pokédex already had a URL.
 */
export function BinderSwitch({ active }) {
  const chip = (to, key, label, end = false) => (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `chip ${active === key || (active === undefined && isActive) ? "active" : ""}`
      }
    >
      {label}
    </NavLink>
  );
  return (
    <div className="chip-row view-switch">
      {chip("/cards", "collection", "Collection", true)}
      {chip("/pokedex", "pokedex", "Pokédex")}
      {chip("/binders", "binders", "Binders")}
    </div>
  );
}

const abbrevRarity = (r) =>
  r ? r.split(/\s+/).map((w) => w[0]).join("").toUpperCase() : "";

/** The shape of a binder, with the fallbacks a binder made before it had one
 *  needs. Three of nine is the common page and what everything defaulted to. */
export const shapeOf = (b) => ({
  rows: Math.max(1, b?.rows || 3),
  cols: Math.max(1, b?.cols || 3),
  double: !!b?.double_page,
  color: b?.color || null,
});

/** Cut a flat list of slots into pages, and pages into facing pairs.
 *
 *  Returns spreads rather than pages so the caller does not have to know
 *  whether it is drawing one page or two — a single-page binder is a list of
 *  spreads that happen to hold one page each, and the markup is the same
 *  either way.
 */
export function paginate(entries, { rows, cols, double }) {
  if (!entries.length) return [];
  const per = Math.max(1, rows * cols);
  const pages = [];
  for (let i = 0; i < entries.length; i += per) pages.push(entries.slice(i, i + per));
  if (!double) return pages.map((p) => [p]);
  const spreads = [];
  for (let i = 0; i < pages.length; i += 2) spreads.push(pages.slice(i, i + 2));
  return spreads;
}

/** A binder drawn as the object it is: pockets to a page, pages in the order
 *  you turn them, and an edge in the colour of the cover.
 *
 *  This replaced a slider. A slider draws a list at whatever width reads best
 *  today, which is the right answer for a list and the wrong one for a
 *  binder — "third row of the fourth page" is a position somebody can point
 *  at, and a grid that reflows to taste has no positions to point at.
 *
 *  `children` is called per entry, so each page keeps whatever tile and
 *  expanding panel its caller already draws.
 */
export function BinderPages({ binder, entries, children, arranging }) {
  const shape = shapeOf(binder);
  const spreads = paginate(entries, shape);
  let page = 0;
  return (
    <div
      className={`binder-book ${shape.double ? "spread" : ""}`}
      style={shape.color ? { "--binder-edge": shape.color } : undefined}
    >
      {spreads.map((spread, i) => (
        <div className="binder-spread" key={i}>
          {spread.map((slots, j) => {
            page += 1;
            return (
              <div className="binder-page" key={j} data-page={page}>
                <div
                  className={`dex-grid cols-${shape.cols} ${arranging ? "arranging" : ""}`}
                  style={{
                    gridTemplateColumns: `repeat(${shape.cols}, minmax(0, 1fr))`,
                  }}
                >
                  {slots.map(children)}
                </div>
                {/* A bordered block with no number is a block; finding the
                    page you meant is the reason the pages are drawn at all. */}
                <span className="binder-page-no">{page}</span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

/** One slot, drawn the way the Pokédex draws one.
 *
 *  Shared so the three kinds of binder cannot drift into looking like three
 *  different features. What differs between them is what fills a slot and
 *  what you can do to it, which is the caller's business, not this one's.
 */
export function BinderSlotTile({ entry, open, onToggle, onName, lifted, arranging }) {
  const state = entry.state; // missing | upgrade | have | one
  const cls = state === "missing" ? "unowned" : state === "upgrade" ? "partial" : "owned";
  const art = entry.card?.image_url || entry.art;

  return (
    <button
      className={`dex-slot ${cls} ${entry.blank ? "blank" : ""} ${lifted ? "lifted" : ""}`}
      aria-expanded={arranging ? undefined : open}
      aria-pressed={arranging ? !!lifted : undefined}
      data-slot={entry.key}
      onClick={onToggle}
    >
      <span className="dex-no">{entry.label}</span>
      {art ? (
        // A set binder shows the art of a card you do not own, dimmed by the
        // slot's own state — the gap should look like the card it wants.
        <img src={art} alt={entry.name || ""} loading="lazy" />
      ) : (
        <span className="placeholder" data-label="" />
      )}
      <span
        className={`name ${onName && !arranging ? "linked" : ""}`}
        title={onName && entry.name && !arranging ? `Find ${entry.name} cards` : undefined}
        onClick={onName && !arranging ? (ev) => onName(ev, entry.name) : undefined}
      >
        {/* the dash means "this wants a name and has not got one"; a blank
            page does not want one, and the outline already says so */}
        {entry.blank ? "" : entry.name || "—"}
      </span>
      <span className="layer-pips">
        {entry.card?.set_abbr && (
          <span className="set-abbr" title={entry.card.set_name}>
            {entry.card.set_abbr}
          </span>
        )}
        {/* The symbol the card actually prints — a circle, a diamond, one or
            more stars — rather than initials nobody says out loud. The tone
            carries the rest: two black stars is a double rare, two silver an
            ultra rare, and that is exactly how the card tells them apart. */}
        {entry.rarity_mark ? (
          <span
            className={`rarity-mark ${entry.rarity_mark.tone}`}
            title={entry.rarity_mark.name}
          >
            {entry.rarity_mark.glyph}
          </span>
        ) : (
          entry.card?.rarity && (
            <span className="rarity-tag" title={entry.card.rarity}>
              {abbrevRarity(entry.card.rarity)}
            </span>
          )
        )}
      </span>
    </button>
  );
}
