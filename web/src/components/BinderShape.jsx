import { Icon } from "./Icons.jsx";

/** The presets people actually own.
 *
 *  A binder is bought, not designed, and almost every one on a shelf is one
 *  of these four. Offering them by name means the common answer is one press
 *  and nobody has to work out that a nine-pocket page is three by three.
 */
const PAGES = [
  { rows: 3, cols: 3, label: "9-pocket" },
  { rows: 4, cols: 3, label: "12-pocket" },
  { rows: 4, cols: 4, label: "16-pocket" },
  { rows: 2, cols: 2, label: "4-pocket" },
];

/** Colours that sit on the app's own dark ground without shouting.
 *
 *  A free colour well is still there for anybody who wants their actual
 *  binder's actual colour; these are so that picking one is a tap rather than
 *  a trip through a system colour dialog on a phone.
 */
const SWATCHES = [
  "#c0392b", "#d97706", "#c9a227", "#3f8f4f",
  "#2f7f8f", "#3b5bdb", "#7048c0", "#b0447f",
  "#5a6472", "#1b1d22",
];

/** How a binder is set up, on the way in and on the way back.
 *
 *  The same control in both places on purpose: a binder you set up wrong is a
 *  binder you want to fix, and a shape you can only choose once is a shape
 *  somebody remakes the binder to change. Nothing here moves a card — rows,
 *  columns and the spread only decide where the page breaks fall — which is
 *  what makes it safe to offer at any time.
 */
export default function BinderShape({ value, onChange, showPages = false, pageHint }) {
  const set = (patch) => onChange({ ...value, ...patch });
  const rows = value.rows ?? 3;
  const cols = value.cols ?? 3;
  const preset = PAGES.find((p) => p.rows === rows && p.cols === cols);

  return (
    <div className="binder-shape">
      <div className="shape-row">
        <span className="shape-label">Page</span>
        <div className="chip-row tight">
          {PAGES.map((p) => (
            <button
              key={p.label}
              type="button"
              className={`chip ${preset === p ? "active" : ""}`}
              onClick={() => set({ rows: p.rows, cols: p.cols })}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="shape-row">
        <span className="shape-label">Pockets</span>
        <div className="shape-dims">
          <label>
            <input
              type="number"
              min="1"
              max="10"
              value={cols}
              onChange={(e) => set({ cols: Number(e.target.value) || 1 })}
            />
            <span>across</span>
          </label>
          <span className="times">×</span>
          <label>
            <input
              type="number"
              min="1"
              max="10"
              value={rows}
              onChange={(e) => set({ rows: Number(e.target.value) || 1 })}
            />
            <span>down</span>
          </label>
          <span className="shape-total">{rows * cols} a page</span>
        </div>
      </div>

      <div className="shape-row">
        <span className="shape-label">Opens as</span>
        <div className="chip-row tight">
          <button
            type="button"
            className={`chip ${!value.double_page ? "active" : ""}`}
            onClick={() => set({ double_page: false })}
          >
            One page
          </button>
          <button
            type="button"
            className={`chip ${value.double_page ? "active" : ""}`}
            onClick={() => set({ double_page: true })}
          >
            Two facing
          </button>
        </div>
      </div>

      {showPages && (
        <div className="shape-row">
          <span className="shape-label">Pages</span>
          <div className="shape-dims">
            <label>
              <input
                type="number"
                min="0"
                max="200"
                value={value.pages ?? 0}
                onChange={(e) => set({ pages: Number(e.target.value) || 0 })}
              />
              <span>pages</span>
            </label>
            <span className="shape-total">
              {(value.pages || 0) * rows * cols} pockets
            </span>
          </div>
        </div>
      )}
      {showPages && (
        <p className="settings-note">
          {pageHint ||
            "Sets it up empty at that size, so you can fill the pockets where " +
              "the cards actually go. Leave it at zero for a binder that just " +
              "grows as you add to it."}
        </p>
      )}

      <div className="shape-row">
        <span className="shape-label">Cover</span>
        <div className="shape-colors">
          {SWATCHES.map((c) => (
            <button
              key={c}
              type="button"
              className={`swatch ${value.color === c ? "on" : ""}`}
              style={{ background: c }}
              title={c}
              aria-label={`Cover colour ${c}`}
              onClick={() => set({ color: value.color === c ? null : c })}
            />
          ))}
          <label className="swatch custom" title="Any other colour">
            <input
              type="color"
              value={value.color || "#3b5bdb"}
              onChange={(e) => set({ color: e.target.value })}
            />
            <Icon id="pencil" />
          </label>
          {value.color && (
            <button
              type="button"
              className="ghost tiny"
              onClick={() => set({ color: null })}
              title="Back to the colour the shelf picks"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
