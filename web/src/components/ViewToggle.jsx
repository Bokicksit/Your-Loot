import { Icon } from "./Icons.jsx";
import { useSettings } from "../settings.jsx";

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
