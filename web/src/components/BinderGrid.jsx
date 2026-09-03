import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

/** The row of chips that says which shelf of cards you are looking at.
 *
 *  Routes rather than local state, because a binder is a thing you send
 *  somebody a link to, and because the Pokédex already had a URL.
 */
/** A price the way a person writes one: "$12.40", "$286". Whole dollars drop
 *  the cents — a market price is not a till receipt — but anything under ten
 *  keeps them, because on a fifty-cent common the cents are the whole number.
 *  Dollars only: the price check deals in nothing else. */
export function money(amount) {
  if (amount == null || Number.isNaN(Number(amount))) return "—";
  const n = Number(amount);
  const digits = n < 10 ? 2 : 0;
  return "$" + n.toLocaleString(undefined, {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
}

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

/** Which page you are looking at, and a way to go to another one.
 *
 *  Watches the pages rather than the slots — the Pokédex is 114 pages and
 *  1,025 pockets, and observing the pockets to work out the page would be a
 *  thousand callbacks to answer a question nine of them already answer.
 *
 *  `signal` is anything that means the pages have been redrawn: a filter, a
 *  new shape, the binder finally arriving. The observer is rebuilt then,
 *  because the elements it was holding no longer exist.
 */
export function usePageTracker(signal) {
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!document.querySelector("[data-page]")) return;
    setPage(1);

    /* Whichever page is under a point near the top of the screen.
     *
     * This was an IntersectionObserver watching every page, and it never
     * moved the number for anybody. Asking the document what is at a point is
     * a question with one answer and no bookkeeping — and, unlike a table of
     * cached page offsets, it cannot go stale when a lazily-loaded card image
     * finally arrives and pushes everything below it down.
     *
     * A quarter of the way across rather than the middle, so a spread reports
     * the left-hand page instead of whatever the gutter happens to be over.
     */
    const pick = () => {
      const x = Math.max(1, Math.round(window.innerWidth / 4));
      const el = document.elementFromPoint(x, 140)?.closest?.("[data-page]");
      // Nothing under the point means the toolbar or a gap, not a new page —
      // keeping the last answer beats flickering back to page one.
      if (el) setPage(Number(el.dataset.page));
    };

    let queued = 0;
    const onScroll = () => {
      if (queued) return; // one read per frame, however fast the wheel spins
      queued = requestAnimationFrame(() => {
        queued = 0;
        pick();
      });
    };

    pick();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      if (queued) cancelAnimationFrame(queued);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [signal]);

  // Instant, not smooth. Page 40 of the Pokédex is sixty thousand pixels
  // down; animating that is a journey rather than a jump, and the point of
  // typing a page number is to be there.
  //
  // Says so straight away rather than waiting to be told by the observer: the
  // box follows `page`, so without this it snaps back to where you were for
  // the moment between the scroll and the callback, which reads as the jump
  // having failed.
  const goTo = (n) => {
    const el = document.querySelector(`[data-page="${n}"]`);
    if (!el) return;
    setPage(n);
    el.scrollIntoView({ block: "start", behavior: "auto" });
  };

  return [page, goTo];
}

/** "12 of 62" — where you are, and somewhere to type where you'd rather be.
 *
 *  The number is the control. A separate "go to page" field beside a "page 12
 *  of 62" label would be two things saying one thing, and on a phone there is
 *  no room for the second.
 */
export function PageBox({ page, total, onGo }) {
  const [draft, setDraft] = useState(String(page));
  const [typing, setTyping] = useState(false);

  // follow the scroll, unless the cursor is in it — nothing worse than a
  // field that rewrites what you are typing
  useEffect(() => {
    if (!typing) setDraft(String(page));
  }, [page, typing]);

  // one page is not somewhere you can be lost
  if (!total || total < 2) return null;

  /** Read the field, not the state.
   *
   *  `draft` is a render behind whatever was just typed, so a commit that
   *  arrives in the same tick as the keystroke — paste then Enter, a password
   *  manager, anything faster than a re-render — would jump to the previous
   *  number. The element always has the current one.
   */
  const commit = (el) => {
    const n = Math.min(Math.max(parseInt(el.value, 10) || 1, 1), total);
    setDraft(String(n));
    setTyping(false);
    onGo(n);
  };

  return (
    <label className="page-box" title={`Page ${page} of ${total} — type one to go there`}>
      <input
        type="number"
        min="1"
        max={total}
        value={draft}
        aria-label="Page"
        onFocus={(e) => {
          setTyping(true);
          e.target.select(); // typing over it is the point; no backspacing first
        }}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={(e) => commit(e.target)}
        onKeyDown={(e) => {
          if (e.key !== "Enter") return;
          e.preventDefault();
          // Jump here rather than leaving it to the blur this triggers.
          // Relying on the blur means Enter does nothing at all anywhere the
          // blur does not arrive, and committing the same number twice is the
          // same jump twice, which is no jump at all.
          commit(e.target);
          e.target.blur();
        }}
      />
      <span>of {total}</span>
    </label>
  );
}

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
export function BinderPages({ binder, entries, children, arranging, flat }) {
  const shape = shapeOf(binder);

  /* Searching does not produce pages, it produces matches.
   *
   * Drawn as pages they were numbered 1, 2, 3 — the position of the results
   * in the result list, which said "page 1" for a card sitting on page 15.
   * A frame around a handful of cards from all over the binder is not a page
   * of it, so while a search is on there are no frames, and each card says
   * where it really lives instead.
   */
  if (flat) {
    return (
      <div className="dex-grid results" data-results="">
        {entries.map(children)}
      </div>
    );
  }

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
/** Where a slot lives in the binder, counted from the binder's own order.
 *
 *  Its index in the unfiltered list, never in whatever is on screen — that is
 *  the whole point: it has to survive a search that shows nine cards from
 *  nine different pages.
 */
export function pageIndex(entries, binder, keyOf) {
  const per = Math.max(1, shapeOf(binder).rows * shapeOf(binder).cols);
  const at = new Map();
  entries.forEach((e, i) => at.set(keyOf(e), Math.floor(i / per) + 1));
  return at;
}

export function BinderSlotTile({ entry, open, onToggle, onName, lifted, arranging, price }) {
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
      {/* only while searching: on the binder proper you are already looking
          at the page, and a badge on every card would say so ninety times */}
      {entry.page ? <span className="slot-page">p.{entry.page}</span> : null}
      {/* a pocket holding spares says how many, the way the card list does */}
      {entry.count > 1 ? (
        <span className="stack-badge" title={`${entry.count} of this card in this pocket`}>
          ×{entry.count}
        </span>
      ) : null}
      {/* The price check, while it is on. `undefined` is "not asked";
          `null` is "asked, and this card is on no marketplace" — the dash
          says so, because a slot that stays silent looks like it was
          missed rather than answered. */}
      {price !== undefined && (
        <span
          className={`slot-price ${price ? "priced" : "none"}`}
          title={
            price
              ? `${price.source} market price` +
                (price.variant ? ` · ${price.variant}` : "") +
                (price.low != null && price.high != null
                  ? ` · ${money(price.low)}–${money(price.high)}`
                  : "")
              : "No price data found — this card is not listed on TCGplayer"
          }
        >
          {price ? money(price.amount) : "No price data"}
        </span>
      )}
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
