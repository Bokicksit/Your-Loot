import { NavLink } from "react-router-dom";
import { Icon } from "./Icons.jsx";

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

/** One slot, drawn the way the Pokédex draws one.
 *
 *  Shared so the three kinds of binder cannot drift into looking like three
 *  different features. What differs between them is what fills a slot and
 *  what you can do to it, which is the caller's business, not this one's.
 */
export function BinderSlotTile({ entry, open, onToggle, onName }) {
  const state = entry.state; // missing | upgrade | have | one
  const cls = state === "missing" ? "unowned" : state === "upgrade" ? "partial" : "owned";
  const art = entry.card?.image_url || entry.art;

  return (
    <button
      className={`dex-slot ${cls}`}
      aria-expanded={open}
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
        className={`name ${onName ? "linked" : ""}`}
        title={onName && entry.name ? `Find ${entry.name} cards` : undefined}
        onClick={onName ? (ev) => onName(ev, entry.name) : undefined}
      >
        {entry.name || "—"}
      </span>
      <span className="layer-pips">
        {entry.card?.set_abbr && (
          <span className="set-abbr" title={entry.card.set_name}>
            {entry.card.set_abbr}
          </span>
        )}
        {entry.card?.rarity && (
          <span className="rarity-tag" title={entry.card.rarity}>
            {abbrevRarity(entry.card.rarity)}
          </span>
        )}
        {entry.final && entry.card && (
          <span className="pip-happy" title="The one">
            <Icon id="check" />
          </span>
        )}
      </span>
    </button>
  );
}
