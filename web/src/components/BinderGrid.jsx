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
export function BinderSlotTile({ entry, open, onToggle, onName, lifted, arranging }) {
  const state = entry.state; // missing | upgrade | have | one
  const cls = state === "missing" ? "unowned" : state === "upgrade" ? "partial" : "owned";
  const art = entry.card?.image_url || entry.art;

  return (
    <button
      className={`dex-slot ${cls} ${lifted ? "lifted" : ""}`}
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
        {entry.name || "—"}
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
        {entry.final && entry.card && (
          <span className="pip-happy" title="The one">
            <Icon id="check" />
          </span>
        )}
      </span>
    </button>
  );
}
