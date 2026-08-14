import { Fragment, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { BinderSlotTile, BinderSwitch } from "../components/BinderGrid.jsx";
import { TileDensity, useTileCols } from "../components/ViewToggle.jsx";
import useDismiss from "../useDismiss.js";

/** One binder — a set, or one you built yourself.
 *
 *  The Pokédex has its own page still, and deliberately: its slots are filled
 *  by choosing between the cards you own, so it needs a picker these two do
 *  not. Here a set slot is filled by owning the card and a custom slot by
 *  putting it there, and neither has anything to choose.
 */
export default function BinderPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all"); // all | missing | have
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(null);
  const [error, setError] = useState(null);
  const [renaming, setRenaming] = useState(false);
  const [cols] = useTileCols("binder", 3, 6);

  useDismiss(
    open !== null,
    () => setOpen(null),
    (t) => t.closest?.("[data-slot]")?.dataset.slot === String(open),
  );

  const load = () =>
    api.binder(id).then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    setData(null);
    setOpen(null);
    load();
  }, [id]);

  if (error) {
    return (
      <div>
        <BinderSwitch active="binders" />
        <p className="error">
          <Icon id="alert" />
          {error}
        </p>
      </div>
    );
  }
  if (!data) return <p className="empty">Loading…</p>;

  const { binder, entries } = data;
  const isCustom = binder.kind === "custom";

  const shown = entries.filter((e) => {
    if (filter === "missing" && e.card) return false;
    if (filter === "have" && !e.card) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      (e.name || "").toLowerCase().includes(q) ||
      (e.label || "").toLowerCase().includes(q) ||
      (e.key || "").toLowerCase().includes(q)
    );
  });

  const remove = async (slotId) => {
    await api.binderRemoveSlot(binder.id, slotId);
    load();
  };

  const move = async (slotId, by) => {
    const ids = entries.map((e) => Number(e.key));
    const at = ids.indexOf(Number(slotId));
    const to = at + by;
    if (at < 0 || to < 0 || to >= ids.length) return;
    [ids[at], ids[to]] = [ids[to], ids[at]];
    setData({ ...data, entries: ids.map((i) => entries.find((e) => Number(e.key) === i)) });
    await api.binderReorder(binder.id, ids);
    load();
  };

  const toggleHappy = async (e) => {
    await api.binderSlotHappy(binder.id, e.key, !e.final);
    load();
  };

  const scrap = async () => {
    if (!window.confirm(`Delete the binder “${binder.name}”? The cards stay in your collection.`))
      return;
    await api.deleteBinder(binder.id);
    navigate("/binders");
  };

  return (
    <div>
      <BinderSwitch active="binders" />

      <div className="toolbar">
        <label className="searchbox">
          <Icon id="search" />
          <input
            type="search"
            placeholder={isCustom ? "Search this binder…" : "Name or number…"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <span className="count">
            {binder.filled}/{binder.total}
          </span>
        </label>
        <button className="ghost" onClick={() => setRenaming(!renaming)} title="Rename">
          <Icon id="pencil" />
        </button>
        <button className="ghost" onClick={scrap} title="Delete this binder">
          <Icon id="trash" />
        </button>
      </div>

      {renaming && (
        <Rename
          binder={binder}
          onDone={() => {
            setRenaming(false);
            load();
          }}
        />
      )}

      <div className="chip-row">
        {[
          ["all", `All (${binder.total})`],
          ["missing", `Missing (${binder.missing})`],
          ["have", `Have (${binder.filled})`],
        ].map(([k, label]) => (
          <button
            key={k}
            className={`chip ${filter === k ? "active" : ""}`}
            onClick={() => setFilter(k)}
          >
            {label}
          </button>
        ))}
        <span className="rail-spacer" />
        <TileDensity module="binder" min={3} max={6} />
      </div>

      {isCustom && entries.length === 0 && (
        <p className="empty">
          Nothing in here yet. Open a card in your collection and add it to this
          binder, or use the button on the Cards page.
        </p>
      )}

      <div
        className={`dex-grid cols-${cols}`}
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {shown.map((e) => (
          <Fragment key={e.key}>
            <BinderSlotTile
              entry={e}
              open={open === e.key}
              onToggle={() => setOpen(open === e.key ? null : e.key)}
            />
            {open === e.key && (
              <div className="dex-detail" data-slot={e.key}>
                <h3>
                  {e.label} {e.name || ""}
                </h3>
                {e.card ? (
                  <dl className="kv">
                    {e.card.set_name && (
                      <>
                        <dt>Set</dt>
                        <dd>{e.card.set_name}</dd>
                      </>
                    )}
                    {e.card.rarity && (
                      <>
                        <dt>Rarity</dt>
                        <dd>{e.card.rarity}</dd>
                      </>
                    )}
                    {e.card.condition && (
                      <>
                        <dt>Condition</dt>
                        <dd>
                          {[e.card.grader, e.card.grade].filter(Boolean).join(" ") ||
                            e.card.condition}
                        </dd>
                      </>
                    )}
                  </dl>
                ) : (
                  <p className="settings-note">
                    Not in your collection yet.
                  </p>
                )}
                <div className="form-row wrap">
                  {e.card && (
                    <button
                      className={`toggle ${e.final ? "on" : ""}`}
                      onClick={() => toggleHappy(e)}
                      title="The copy you want here"
                    >
                      {e.final ? "The one" : "Mark as the one"}
                    </button>
                  )}
                  {!e.card && e.name && (
                    <button
                      className="ghost"
                      onClick={() => navigate(`/cards?add=${encodeURIComponent(e.name)}`)}
                    >
                      <Icon id="search" />
                      Find this card
                    </button>
                  )}
                  {isCustom && (
                    <>
                      <button className="ghost" onClick={() => move(e.key, -1)} title="Move earlier">
                        <Icon id="back" />
                      </button>
                      <button className="ghost flip" onClick={() => move(e.key, 1)} title="Move later">
                        <Icon id="back" />
                      </button>
                      <button className="ghost" onClick={() => remove(e.key)}>
                        <Icon id="trash" />
                        Take out
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function Rename({ binder, onDone }) {
  const [name, setName] = useState(binder.name);
  const save = async (e) => {
    e.preventDefault();
    if (name.trim() && name.trim() !== binder.name) {
      await api.renameBinder(binder.id, name.trim());
    }
    onDone();
  };
  return (
    <form className="filter-sheet" onSubmit={save}>
      <label>
        <span>Call it</span>
        <input
          type="text"
          className="grow"
          autoFocus
          maxLength={60}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <button type="submit" className="primary">
        <Icon id="check" />
        Save
      </button>
    </form>
  );
}
