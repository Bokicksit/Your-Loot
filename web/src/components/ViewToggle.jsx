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
    if (w < 420) return 2;
    if (w < 620) return 3;
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
export function useTileCols(module) {
  const [stored, setStored] = useListPref(module, "tileCols", 3);
  const max = useMaxCols();
  return [Math.min(Number(stored) || 3, max), setStored, max];
}

/** The slider. Only worth showing when there are tiles to space out, so the
 *  pages render it beside the toggle and only in tile mode. */
export function TileDensity({ module }) {
  const [cols, setCols, max] = useTileCols(module);
  if (max < 3) return null; // a phone in portrait has one sensible answer
  return (
    <label className="tile-density" title="Tiles per row">
      <input
        type="range"
        min="2"
        max={max}
        step="1"
        value={cols}
        onChange={(e) => setCols(Number(e.target.value))}
        aria-label="Tiles per row"
      />
      <span className="tile-density-n">{cols}</span>
    </label>
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
 */
export default function ViewToggle({ module }) {
  const [tiles, setTiles] = useTileView(module);
  return (
    <div className="view-toggle" role="group" aria-label="Layout">
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
