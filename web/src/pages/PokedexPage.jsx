import { Fragment, useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

// Pokédex grid: one slot per national dex number, owned slots in gold.
// Tapping a slot opens a full-width detail strip listing that Pokémon's cards.
export default function PokedexPage() {
  const [entries, setEntries] = useState([]);
  const [ownedOnly, setOwnedOnly] = useState(false);
  const [open, setOpen] = useState(null); // dex_no of expanded slot

  useEffect(() => {
    api.pokedex(ownedOnly).then((d) => setEntries(d.entries));
  }, [ownedOnly]);

  return (
    <div>
      <div className="toolbar">
        <button
          type="button"
          className={`toggle ${ownedOnly ? "on" : ""}`}
          onClick={() => setOwnedOnly(!ownedOnly)}
        >
          Owned only
        </button>
        <span className="count" style={{ marginLeft: "auto" }}>
          {entries.filter((e) => e.owned_count > 0).length} / {entries.length}
        </span>
      </div>
      <div className="dex-grid">
        {entries.map((e) => (
          <Fragment key={e.dex_no}>
            <button
              className={`dex-slot ${e.owned_count ? "owned" : "unowned"}`}
              aria-expanded={open === e.dex_no}
              onClick={() => setOpen(open === e.dex_no ? null : e.dex_no)}
            >
              <span className="dex-no">#{String(e.dex_no).padStart(3, "0")}</span>
              {e.display_image ? (
                <img src={e.display_image} alt={e.display_title} loading="lazy" />
              ) : (
                <span className="placeholder" data-label="no art" />
              )}
              <span className="name">{e.display_title}</span>
              <span className="count">
                {e.owned_count} / {e.card_count}
              </span>
            </button>
            {open === e.dex_no && (
              <div className="dex-detail">
                <h3>
                  #{String(e.dex_no).padStart(3, "0")} {e.display_title} —{" "}
                  {e.owned_count} owned
                </h3>
                <ul>
                  {e.cards.map((c) => (
                    <li key={c.id}>
                      <span className="module-chip"><Icon id="card" /></span>
                      {c.attrs.set_name} #{c.attrs.card_number}
                      {c.attrs.variant && c.attrs.variant !== "normal"
                        ? ` · ${c.attrs.variant}`
                        : ""}
                      {c.wanted ? " ★" : ""}
                      <span className="dex-no">
                        {c.owned.length ? `×${c.owned.length}` : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
