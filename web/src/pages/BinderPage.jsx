import { Fragment, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { BinderSlotTile, BinderSwitch } from "../components/BinderGrid.jsx";
import { TileDensity, useTileCols } from "../components/ViewToggle.jsx";
import useDismiss from "../useDismiss.js";
import ImagePicker from "../components/ImagePicker.jsx";

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
  const [picking, setPicking] = useState(false);
  const [arranging, setArranging] = useState(false);
  const [lifted, setLifted] = useState(null); // the card in your hand
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

  /** Two taps to move a card anywhere: one to lift it, one to say where.
   *
   *  Not drag-and-drop. This is a grid that is usually read on a phone, where
   *  dragging means fighting the scroll and hitting a target the size of a
   *  fingernail; and a binder of thirty is thirty positions to drag across.
   *  Tapping twice costs the same whether the card moves one place or twenty.
   */
  const place = async (targetKey) => {
    const ids = entries.map((e) => Number(e.key));
    const from = ids.indexOf(Number(lifted));
    const to = ids.indexOf(Number(targetKey));
    setLifted(null);
    if (from < 0 || to < 0 || from === to) return;
    const [moved] = ids.splice(from, 1);
    ids.splice(to, 0, moved);
    // redraw before the round trip: the tap should feel like it landed
    setData({ ...data, entries: ids.map((i) => entries.find((e) => Number(e.key) === i)) });
    await api.binderReorder(binder.id, ids);
    load();
  };

  const tapSlot = (e) => {
    if (!arranging) {
      setOpen(open === e.key ? null : e.key);
      return;
    }
    if (lifted === null) setLifted(e.key);
    else if (lifted === e.key) setLifted(null);
    else place(e.key);
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
        <span className="binder-actions">
        {isCustom && (
          <button className="primary" onClick={() => setPicking(!picking)}>
            <Icon id="plus" />
            Add cards
          </button>
        )}
        {isCustom && entries.length > 1 && (
          <button
            className={`ghost ${arranging ? "on" : ""}`}
            onClick={() => {
              setArranging(!arranging);
              setLifted(null);
              setOpen(null);
            }}
            title="Change the order"
          >
            <Icon id="sliders" />
            {arranging ? "Done" : "Arrange"}
          </button>
        )}
        <button
          className={`ghost ${renaming ? "on" : ""}`}
          onClick={() => setRenaming(!renaming)}
          title="Rename this binder or give it a cover"
        >
          <Icon id="pencil" />
        </button>
        <button className="ghost" onClick={scrap} title="Delete this binder">
          <Icon id="trash" />
        </button>
        </span>
      </div>

      {renaming && (
        <Rename
          binder={binder}
          onCover={load}
          onDone={() => {
            setRenaming(false);
            load();
          }}
        />
      )}

      {/* One of three, always — which is what a segmented track says and a row
          of separate buttons only implies. */}
      <div className="segmented">
        {[
          ["all", "All", binder.total],
          ["missing", "Missing", binder.missing],
          ["have", "Have", binder.filled],
        ].map(([k, label, n]) => (
          <button
            key={k}
            className={`chip ${filter === k ? "active" : ""}`}
            onClick={() => setFilter(k)}
          >
            {label}
            <span className="seg-n">{n}</span>
          </button>
        ))}
      </div>

      {/* Its own row, as on the Pokédex. Sharing a line with the filter chips
          pushed it 49px off the right edge of a phone — the "3 up" label was
          not on screen at all and the slider had to be scrolled to. */}
      <div className="chip-row">
        <span className="rail-spacer" />
        <TileDensity module="binder" min={3} max={6} />
      </div>

      {isCustom && picking && (
        <AddCards
          binder={binder}
          already={entries.map((e) => e.card?.owned_id).filter(Boolean)}
          onAdded={load}
          onClose={() => setPicking(false)}
        />
      )}

      {isCustom && entries.length === 0 && !picking && (
        <p className="empty">
          Nothing in here yet — press <strong>Add cards</strong> and pick from
          what you own.
        </p>
      )}

      {arranging && (
        <p className="settings-note arrange-hint">
          {lifted === null
            ? "Tap a card to pick it up."
            : "Now tap where it should go — or tap it again to put it back."}
        </p>
      )}

      <div
        className={`dex-grid cols-${cols} ${arranging ? "arranging" : ""}`}
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {shown.map((e) => (
          <Fragment key={e.key}>
            <BinderSlotTile
              entry={e}
              open={open === e.key}
              lifted={lifted === e.key}
              arranging={arranging}
              onToggle={() => tapSlot(e)}
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

/** Name and cover.
 *
 *  The cover saves as soon as it is chosen rather than waiting for the form:
 *  ImagePicker has already uploaded the file or copied the link by then, so
 *  leaving without pressing Save would strand a picture on the server that
 *  nothing points at.
 */
function Rename({ binder, onDone, onCover }) {
  const [name, setName] = useState(binder.name);
  const save = async (e) => {
    e.preventDefault();
    if (name.trim() && name.trim() !== binder.name) {
      await api.editBinder(binder.id, { name: name.trim() });
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
      <span className="settings-label">Cover</span>
      <p className="settings-note">
        A photo of the real binder, or any picture — upload one, take one, or
        paste a link. It shows beside the name on your shelf.
      </p>
      <ImagePicker
        label="Cover"
        value={binder.image_url}
        onChange={async (url) => {
          await api.editBinder(binder.id, { image_url: url || "" });
          onCover?.();
        }}
      />
      <button type="submit" className="primary">
        <Icon id="check" />
        Save
      </button>
    </form>
  );
}

/** Pick from what you own.
 *
 *  A copy, not a card: you might own three of the same Charizard and put a
 *  different one in each binder, so the thing being filed has to be the
 *  physical copy. Copies already in this binder are shown greyed rather than
 *  hidden — a list that silently omits what you are looking for reads as a
 *  search that failed.
 */
function AddCards({ binder, already, onAdded, onClose }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(null);
  const [added, setAdded] = useState([]);
  const [error, setError] = useState(null);
  const inBinder = new Set([...already, ...added]);

  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      api
        // include_binder, because the cards worth filing are usually the ones
        // already on display somewhere
        .cards({ search: q.trim(), include_binder: true, limit: 60 })
        .then((d) => live && setRows(d.items))
        .catch((e) => live && setError(e.message));
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q]);

  const copies = (rows || []).flatMap((card) =>
    (card.owned || []).map((o) => ({ card, owned: o })),
  );

  const add = async (ownedId) => {
    setBusy(ownedId);
    setError(null);
    try {
      await api.binderAddCards(binder.id, [ownedId]);
      setAdded((a) => [...a, ownedId]);
      onAdded();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="filter-sheet">
      <label>
        <span>Add to “{binder.name}”</span>
        <input
          type="search"
          className="grow"
          autoFocus
          placeholder="Search your cards…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </label>
      {error && <p className="error">{error}</p>}
      {rows === null ? (
        <p className="empty">Loading…</p>
      ) : (
        <div className="set-picker">
          {copies.map(({ card, owned }) => {
            const inIt = inBinder.has(owned.id);
            return (
              <button
                key={owned.id}
                type="button"
                className="set-row"
                disabled={inIt || busy === owned.id}
                onClick={() => add(owned.id)}
              >
                <span className="set-name">
                  {card.title}
                  {card.attrs?.card_number && <em> #{card.attrs.card_number}</em>}
                </span>
                <span className="set-meta">
                  {card.attrs?.set_name || ""}
                  {owned.condition && ` · ${owned.condition}`}
                  {inIt && <strong> · in this binder</strong>}
                </span>
              </button>
            );
          })}
          {copies.length === 0 && (
            <p className="empty">
              {q.trim() ? "Nothing of yours matches that." : "No cards owned yet."}
            </p>
          )}
        </div>
      )}
      <button type="button" className="ghost" onClick={onClose}>
        Done
      </button>
    </div>
  );
}
