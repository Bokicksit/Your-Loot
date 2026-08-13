import { Icon } from "./Icons.jsx";
import { useEffect, useState } from "react";
import { useSettings, useListPref } from "../settings.jsx";

/** Modules that render as tiles. Cards started that way and everything else
 *  started as rows, so that's the default — a toggle nobody touches leaves the
 *  app exactly as it was. */
export function useTileView(module) {
  const { settings, save } = useSettings();
  // settings is null until the first load resolves; assume the default rather
  // than flashing the wrong layout and reflowing once it arrives
  const list = settings?.tile_modules ?? (module === "cards" ? [module] : []);
  const tiles = list.includes(module);
  const setTiles = (on) =>
    save({
      tile_modules: on
        ? [...new Set([...list, module])]
        : list.filter((m) => m !== module),
    });
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
    if (w < 620) return 4;
    if (w < 900) return 4;
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

/** Tiles per row, per collection. Three is what the grid used to settle on by
 *  itself, so a slider nobody touches changes nothing. */
export function useTileCols(module, min = 2) {
  const [stored, setStored] = useListPref(module, "tileCols", Math.max(3, min));
  const max = useMaxCols();
  // clamped both ways: a stored 2 from before a floor was raised must not
  // render a column count the slider can no longer express
  const cols = Math.min(Math.max(Number(stored) || 3, min), Math.max(min, max));
  return [cols, setStored, Math.max(min, max), min];
}

/** The slider. Only worth showing when there are tiles to space out, so the
 *  pages render it beside the toggle and only in tile mode. */
export function TileDensity({ module, min = 2 }) {
  const [cols, setCols, max] = useTileCols(module, min);
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
