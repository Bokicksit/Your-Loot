import { Icon } from "./Icons.jsx";
import { useEffect, useState } from "react";
import { useSettings, useListPref } from "../settings.jsx";

/** Modules that render as tiles. Cards started that way and everything else
 *  started as rows, so that's the default — a toggle nobody touches leaves the
 *  app exactly as it was.
 *
 *  A binder is on that list because it has never been anything but a grid:
 *  giving it a toggle should offer a list, not quietly switch it to one. */
const TILES_BY_DEFAULT = new Set(["cards", "binder"]);

/** A module that defaults to tiles needs its *off* state written down.
 *
 *  The list only ever recorded which modules are tiled, so "not in the list"
 *  meant both "never chosen" and "turned off" — fine while cards was the only
 *  default, because cards was always written in. Adding the binder broke it:
 *  every existing install has a list that predates the binder, so it read as
 *  "turned off" and the binder would have silently become a list the first
 *  time somebody loaded it.
 *
 *  So switching one of these off stores `!binder`. Old lists are untouched
 *  and still mean what they meant.
 */
const off = (module) => `!${module}`;

export function useTileView(module) {
  const { settings, save } = useSettings();
  // settings is null until the first load resolves; assume the default rather
  // than flashing the wrong layout and reflowing once it arrives
  const list = settings?.tile_modules ?? [];
  const tiles = list.includes(module)
    || (TILES_BY_DEFAULT.has(module) && !list.includes(off(module)));
  const setTiles = (on) => {
    const without = list.filter((m) => m !== module && m !== off(module));
    save({ tile_modules: on ? [...without, module] : [...without, off(module)] });
  };
  return [tiles, setTiles];
}


/** How many will actually fit, whatever you asked for.
 *
 *  Six across is right on a desk and unreadable on a phone, so the ceiling
 *  follows the window. The slider's maximum moves with it rather than the grid
 *  quietly ignoring the number you set — being told you cannot have six is
 *  better than picking six and getting three.
 */
export function useMaxCols() {
  const cap = () => {
    const w = typeof window === "undefined" ? 1280 : window.innerWidth;
    // Four fits on a portrait phone at about 85px a tile. That is small, but
    // the tile drops to a cover and a name at four, so it is a wall of
    // artwork rather than four squashed rows — and on the screen this app is
    // used on most, that is the view worth being able to reach.
    if (w < 560) return 4;
    // The old steps were 620 and 900, which were guesses and too cautious: at
    // 800px six covers are 133px apiece, comfortably readable, and the ceiling
    // was still holding them at four. Sized from what a tile actually needs —
    // about 120px — rather than from familiar breakpoints.
    if (w < 760) return 5;
    return 6;
  };
  const [max, setMax] = useState(cap);
  useEffect(() => {
    const on = () => setMax(cap());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return max;
}


/** Is there room to put the slider beside the layout toggle?
 *
 *  It wants about 150px of its own, and the rail already carries the filters.
 *  Below this the rail is scrolling sideways, and a control docked inside a
 *  line that scrolls is how the slider ended up sitting on top of a filter in
 *  the first place — so it takes the row underneath instead.
 */
export function useInlineDensity() {
  const max = useMaxCols();
  // 620px, the same width the four-across ceiling uses. 900 was picked to be
  // safe and was simply wrong: on a folded filter row the slider fits beside
  // the toggle with room to spare long before then, and leaving it on a row
  // of its own wasted a whole line to one control.
  return max >= 4;
}

/** Tiles per row, per collection. Three is what the grid used to settle on by
 *  itself, so a slider nobody touches changes nothing. */
export function useTileCols(module, min = 2, ceiling) {
  const [stored, setStored] = useListPref(module, "tileCols", Math.max(3, min));
  // A caller that names its own ceiling gets it outright rather than having it
  // clamped against the screen rule. That rule is sized for covers, and a dex
  // slot is a small numbered square — five of them fit where five box arts
  // would not, which is why the old picker offered 3/4/5 at any width.
  const screenMax = useMaxCols();
  const max = ceiling ?? screenMax;
  // clamped both ways: a stored 2 from before a floor was raised must not
  // render a column count the slider can no longer express
  const cols = Math.min(Math.max(Number(stored) || 3, min), Math.max(min, max));
  return [cols, setStored, Math.max(min, max), min];
}

/** The slider. Only worth showing when there are tiles to space out, so the
 *  pages render it beside the toggle and only in tile mode. */
export function TileDensity({ module, min = 2, max: ceiling }) {
  const [cols, setCols, max] = useTileCols(module, min, ceiling);
  // the track is filled up to the thumb rather than uniformly grey, so the
  // control reads as a quantity instead of a position
  const fill = ((cols - min) / Math.max(1, max - min)) * 100;
  return (
    <div className="density">
      <Icon id="tiles" />
      <input
        type="range"
        min={min}
        max={max}
        step="1"
        value={cols}
        onChange={(e) => setCols(Number(e.target.value))}
        style={{ "--fill": `${fill}%` }}
        aria-label="Tiles per row"
      />
      <span className="density-val">{cols} up</span>
    </div>
  );
}

/** Tiles or rows, per collection.
 *
 *  Both views answer a different question. Tiles are for "what does my shelf
 *  look like" — a wall of covers you recognise by sight. Rows are for "what
 *  exactly do I have" — the platform, the edition, the condition of each copy,
 *  legible without opening anything. Which one is right depends on the
 *  collection and the moment, so it's a per-collection preference rather than
 *  one setting for the whole app.
 *
 *  Drawn as one segmented pill rather than two loose buttons: they are two
 *  halves of a single choice, and gold on the active half says which.
 */
export default function ViewToggle({ module }) {
  const [tiles, setTiles] = useTileView(module);
  return (
    <div className="viewseg" role="group" aria-label="Layout">
      <button
        type="button"
        className={tiles ? "on" : ""}
        onClick={() => setTiles(true)}
        aria-pressed={tiles}
        title="Tiles — bigger pictures"
      >
        <Icon id="tiles" />
      </button>
      <button
        type="button"
        className={!tiles ? "on" : ""}
        onClick={() => setTiles(false)}
        aria-pressed={!tiles}
        title="List — more detail"
      >
        <Icon id="list" />
      </button>
    </div>
  );
}
