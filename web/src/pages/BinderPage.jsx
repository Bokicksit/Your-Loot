import { Fragment, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import {
  BinderPages,
  BinderSlotTile,
  BinderSwitch,
  PageBox,
  money,
  pageIndex,
  paginate,
  shapeOf,
  usePageTracker,
} from "../components/BinderGrid.jsx";
import BinderShape from "../components/BinderShape.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { useHasJapanese, usePublicProfiles } from "../settings.jsx";
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
  const [sort, setSort] = useState("order");
  const [adding, setAdding] = useState(null);   // the slot being filled
  // The price check. `pricing` is the switch; `prices` is what came back for
  // the page on screen — item id to a price, or null for a card that is on
  // no marketplace. Cleared, not kept, when the switch goes off.
  const [pricing, setPricing] = useState(false);
  const [prices, setPrices] = useState(null);

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

  // Above the early returns, because hooks are. The signal is everything that
  // redraws the pages — a different binder, a filter, a search, a sort — so
  // the observer is rebuilt when the elements it holds are replaced.
  const [pageNo, goToPage] = usePageTracker(
    `${id}:${data?.entries.length ?? 0}:${filter}:${query}:${sort}`
  );

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

  /* The Pokédex has a page of its own and this is not it.
   *
   * It was reachable both ways and only one of them could do anything: on
   * /pokedex a name is a link to search for that card and a filled slot can
   * be swapped for a better copy, and here neither existed — a slot with a
   * card in it opened a panel with no buttons at all. That is not a thing
   * anybody chose; the shelf simply linked to a page that never learned what
   * a dex binder can do.
   *
   * Sent there rather than taught it, because the alternative is a second
   * copy of the swap flow that has to stay in step with the first. One
   * Pokédex, one page, and the shelf link goes straight there.
   */
  if (binder.kind === "dex") return <Navigate to="/pokedex" replace />;

  const isCustom = binder.kind === "custom";

  // Sorting looks at the binder differently; it does not rearrange it. That
  // distinction matters most on a custom binder, where the order *is* the
  // binder — so Arrange is only offered while you are looking at it in its
  // own order, rather than letting you drag a card into a position that the
  // sort would immediately move it out of.
  const byName = (a, b) => (a.name || "").localeCompare(b.name || "");
  const sorters = {
    order: null,
    name: byName,
    set: (a, b) =>
      (a.card?.set_name || "￿").localeCompare(b.card?.set_name || "￿") ||
      byName(a, b),
  };

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

  // Whether you are looking at the binder or at a set of results. Sorting is
  // not on this list: A–Z still shows every card, so it is the same binder
  // read in another order, and its pages are still pages.
  const searching = filter !== "all" || query.trim() !== "";

  // Where each slot really lives, from the binder's own order — so a result
  // can say "page 15" while sitting third in a list of matches.
  const homePage = pageIndex(entries, binder, (e) => e.key);
  const ordered = (sorters[sort] ? [...shown].sort(sorters[sort]) : shown).map(
    (e) => (searching ? { ...e, page: homePage.get(e.key) } : e)
  );

  /* The cards the price check is about: the spread on screen, or the results
     while a search is on. Never the whole binder — a custom binder can hold
     hundreds, and the point of a page is that it is a page. */
  const spreadOnScreen = () => {
    if (searching) return ordered.slice(0, 40);
    const spreads = paginate(ordered, shapeOf(binder));
    const per = binder.double_page ? 2 : 1;
    const i = Math.min(spreads.length - 1, Math.max(0, Math.floor((pageNo - 1) / per)));
    return (spreads[i] || []).flat();
  };
  const onScreen = pricing ? spreadOnScreen() : [];
  const idOf = (e) => e.card?.id ?? e.item_id ?? null;
  const priceFor = (e) => {
    if (!pricing || !prices) return undefined;
    // the provider being down is said once, in the bar; a dash on every card
    // would say "unlisted" nine times about cards that were never asked
    if (prices.unavailable) return undefined;
    const id = idOf(e);
    if (id == null || !(id in prices.prices)) return undefined;
    return prices.prices[id];
  };

  const perPage = Math.max(1, (binder.rows || 3) * (binder.cols || 3));
  // Pages of the binder, not of the result list — the box is a way back into
  // the binder, so it counts the binder even while you are looking at matches.
  const pageTotal = Math.ceil(entries.length / perPage);

  const remove = async (slotId) => {
    await api.binderRemoveSlot(binder.id, slotId);
    load();
  };

  /** The name is a link to that card in your collection.
   *
   *  The tile has taken this since it was written and no binder ever passed
   *  it, so the Pokédex had clickable names and the other two did not — the
   *  same tile behaving differently depending on which page drew it. Stops
   *  the tap from also opening the slot's panel underneath.
   */
  const findCards = (ev, name) => {
    ev.stopPropagation();
    if (name) navigate(`/cards?add=${encodeURIComponent(name)}`);
  };

  /** A page with nothing on it, added at the end and picked up straight away.
   *
   *  The lift is the point. A blank page lands last, which on a binder of
   *  forty is a scroll away from wherever you were looking — so it arrives
   *  already in your hand, and the next tap is where it goes. Same two taps as
   *  moving anything else.
   */
  const addBlank = async () => {
    const next = await api.binderAddBlank(binder.id);
    setData(next);
    setLifted(next.entries[next.entries.length - 1]?.key ?? null);
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

  /** "I have this one" — the whole of adding a card, on a set binder.
   *
   *  A set slot names one exact card, and the binder is looking at it. There
   *  is nothing to search for and nothing to choose, so sending somebody to
   *  the Cards page to type the name of a card the app is already showing
   *  them would be asking them to do the computer's job.
   *
   *  It goes into the collection proper, because that is what owning a card
   *  means here — a binder slot is a view of a copy, never a place a copy
   *  lives on its own.
   */
  const addToSlot = async (e) => {
    setAdding(e.key + e.variant);
    try {
      const res = await api.addOwned(e.item_id, {});
      const copy = res.owned?.[res.owned.length - 1];
      // pin it to this printing's slot rather than letting it fall into the
      // first free one — you pressed a particular box
      if (copy && e.variant) {
        await api.binderFillSlot(binder.id, e.key, {
          owned_id: copy.id, item_id: e.item_id, variant: e.variant,
        });
      }
      load();
    } finally {
      setAdding(null);
    }
  };

  const removeFromSlot = async (e) => {
    const what = e.printing ? `${e.name} (${e.printing})` : e.name;
    if (!window.confirm(`Remove ${what} from your collection?`)) return;
    setAdding(e.key + e.variant);
    try {
      await api.removeOwned(e.card.id, e.card.owned_id);
      load();
    } finally {
      setAdding(null);
    }
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
        {/* One card and no way in was the old gate; Arrange is also where an
            empty page is added, and a binder holding a single card is exactly
            where you might want one either side of it. */}
        {isCustom && entries.length > 0 && sort === "order" && (
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
        {/* What the page is worth, laid over the cards while this is on.
            Looked up when you switch it on and forgotten when you switch it
            off — a price is a fact about today. */}
        {entries.length > 0 && (
          <button
            className={`ghost ${pricing ? "on" : ""}`}
            onClick={() => {
              setPricing(!pricing);
              if (pricing) setPrices(null);
            }}
            title="Lay today's market price over every card on this page"
          >
            <Icon id="coin" />
            {pricing ? "Prices on" : "Price check"}
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
        <select
          className="chip-select"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          title="How to lay the binder out — this does not change its order"
        >
          <option value="order">{isCustom ? "Binder order" : "Card number"}</option>
          <option value="name">A–Z</option>
          {isCustom && <option value="set">By set</option>}
        </select>
        <PageBox page={pageNo} total={pageTotal} onGo={goToPage} />
        <span className="rail-spacer" />
        {/* Where the tile slider used to be. How wide a binder is drawn is a
            fact about the binder now, set where the rest of its shape is set,
            rather than a reader preference that made "third row of page four"
            mean something different on every screen. */}
        <span className="binder-shape-note">
          {binder.cols}×{binder.rows}
          {binder.double_page ? " · spread" : ""}
          {binder.pages ? ` · ${binder.pages} page${binder.pages > 1 ? "s" : ""}` : ""}
        </span>
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
        <div className="arrange-bar">
          <p className="settings-note arrange-hint">
            {lifted === null
              ? "Tap a card to pick it up."
              : "Now tap where it should go — or tap it again to put it back."}
          </p>
          <button
            className="ghost"
            onClick={addBlank}
            title="Leave a gap — a page with nothing on it"
          >
            <Icon id="plus" />
            Empty slot
          </button>
        </div>
      )}

      {pricing && (
        <PriceBar
          entries={onScreen}
          prices={prices}
          onPrices={setPrices}
        />
      )}

      <BinderPages
        binder={binder}
        entries={ordered}
        arranging={arranging}
        flat={searching}
      >
        {(e) => (
          <Fragment key={e.key}>
            <BinderSlotTile
              entry={e}
              open={open === e.key}
              lifted={lifted === e.key}
              arranging={arranging}
              price={priceFor(e)}
              onToggle={() => tapSlot(e)}
              onName={findCards}
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
                  {/* What it is worth, from the same sold-listings search the
                      Cards page uses. Sellers title a card by its number and
                      set, never by its rarity, so those are the qualifiers. */}
                  {e.card && (
                    <EbayLink
                      title={e.card.title}
                      terms={[
                        `${e.card.card_number}${
                          e.card.set_total ? `/${e.card.set_total}` : ""
                        }`,
                        e.card.set_name,
                      ]}
                    />
                  )}
                  {/* A set binder knows exactly which card the slot wants, so
                      it can be filled here. The other kinds cannot: a dex slot
                      takes any card of that species and a custom binder takes
                      whatever you choose, and both of those are a search. */}
                  {binder.kind === "set" && !e.card && e.item_id && (
                    <button
                      className="primary"
                      disabled={adding === e.key + e.variant}
                      onClick={() => addToSlot(e)}
                    >
                      <Icon id="plus" />
                      {adding === e.key + e.variant ? "…" : "I have this"}
                    </button>
                  )}
                  {binder.kind === "set" && e.card && (
                    <button
                      className="ghost"
                      disabled={adding === e.key + e.variant}
                      onClick={() => removeFromSlot(e)}
                    >
                      <Icon id="trash" />
                      Remove
                    </button>
                  )}
                  {binder.kind !== "set" && !e.card && e.name && (
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
        )}
      </BinderPages>
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
  const hasJapanese = useHasJapanese();
  const profiles = usePublicProfiles();
  const [name, setName] = useState(binder.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [shape, setShape] = useState({
    rows: binder.rows ?? 3,
    cols: binder.cols ?? 3,
    double_page: !!binder.double_page,
    allow_ja: !!binder.allow_ja,
    on_profile: binder.on_profile !== false,
    color: binder.color || null,
    pages: binder.pages ?? 0,
  });

  /** A set binder can become a master set and go back again.
   *
   *  The slots survive it. A keeper flag is about the card in the slot, and
   *  the plain slot of a master binder is the same slot the simple one had —
   *  switching back and forth must not cost you what you marked.
   */
  const flipMaster = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.editBinder(binder.id, { master: !binder.master });
      onCover?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  /** One PATCH for the lot.
   *
   *  Only what actually changed goes up — a page count sent unchanged on a
   *  binder that has grown since the form opened would be read as "shrink it
   *  back", and the server would rightly refuse to throw the new cards away.
   */
  const save = async (e) => {
    e.preventDefault();
    const patch = {};
    if (name.trim() && name.trim() !== binder.name) patch.name = name.trim();
    if (shape.rows !== (binder.rows ?? 3)) patch.rows = shape.rows;
    if (shape.cols !== (binder.cols ?? 3)) patch.cols = shape.cols;
    if (shape.double_page !== !!binder.double_page) {
      patch.double_page = shape.double_page;
    }
    if (shape.allow_ja !== !!binder.allow_ja) patch.allow_ja = shape.allow_ja;
    if (shape.on_profile !== (binder.on_profile !== false)) {
      patch.on_profile = shape.on_profile;
    }
    if ((shape.color || null) !== (binder.color || null)) {
      patch.color = shape.color || "";
    }
    if (binder.kind === "custom" && shape.pages !== (binder.pages ?? 0)) {
      patch.pages = shape.pages;
    }
    if (!Object.keys(patch).length) return onDone();
    setBusy(true);
    setError(null);
    try {
      await api.editBinder(binder.id, patch);
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
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
      <BinderShape
        value={shape}
        onChange={setShape}
        showPages={binder.kind === "custom"}
        showJapanese={binder.kind === "custom" && hasJapanese}
        showProfile={profiles}
        pageHint={
          "Grows the binder with empty pages, or takes empty ones off the " +
          "end. It will not drop a page that still has a card in it."
        }
      />
      {binder.kind === "set" && (
        <>
          <div className="form-row">
            <span className="settings-label">Master set</span>
            <button
              type="button"
              className={`toggle ${binder.master ? "on" : ""}`}
              disabled={busy}
              onClick={flipMaster}
            >
              {busy ? "…" : binder.master ? "Every printing" : "One per card"}
            </button>
          </div>
          <p className="settings-note">
            {binder.master
              ? "Each card has a slot per printing — plain, reverse holo, holo. Turning this off folds them back into one slot each; nothing you have marked is lost either way."
              : "One slot per card. Turning this on splits each into the ways it was printed, looking the printings up the first time."}
          </p>
        </>
      )}
      {error && <p className="error">{error}</p>}
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

/** The price check's own strip: fetches for the entries it is handed and
 *  totals what came back. A component rather than an effect in the page so
 *  it can use hooks below the page's early returns, and so the page keeps
 *  only the result.
 *
 *  Two totals, because they answer two different questions: what the cards
 *  you own on this page are worth, and what the empty slots would cost to
 *  fill. A set binder has both; a custom binder only ever has the first.
 */
function PriceBar({ entries, prices, onPrices }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(null);

  const ids = entries.map((e) => e.card?.id ?? e.item_id).filter((x) => x != null);
  const key = ids.join(",");

  useEffect(() => {
    if (!ids.length) {
      onPrices({ prices: {}, priced: 0, asked: 0, unavailable: false });
      return;
    }
    let live = true;
    setBusy(true);
    setFailed(null);
    const variants = {};
    for (const e of entries) {
      if (e.card?.id != null) variants[e.card.id] = e.card.variant || null;
    }
    api
      .cardPrices(ids, variants)
      .then((r) => live && onPrices(r))
      .catch((e) => live && setFailed(e.message))
      .finally(() => live && setBusy(false));
    return () => {
      live = false;
    };
    // the ids are the identity of the page; the entries object is rebuilt
    // on every render and would refetch forever
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const priced = (e) => {
    const id = e.card?.id ?? e.item_id;
    const p = prices?.prices?.[id];
    return p && p.currency === "USD" ? p.amount : null;
  };
  let have = 0, gaps = 0, haveN = 0, gapN = 0;
  for (const e of entries) {
    const v = priced(e);
    if (v == null) continue;
    if (e.card) { have += v; haveN += 1; } else { gaps += v; gapN += 1; }
  }
  const updated = Object.values(prices?.prices || {}).find((p) => p?.updated)?.updated;
  const age = updated ? ago(updated) : null;

  return (
    <div className="price-bar" role="status">
      {busy && <span className="note">Checking prices…</span>}
      {!busy && failed && <span className="note warn">{failed}</span>}
      {!busy && !failed && prices?.unavailable && (
        <span className="note warn">
          Prices are unavailable right now — the price service is not answering.
        </span>
      )}
      {!busy && !failed && prices && !prices.unavailable && (
        <>
          <span className="sum">
            {money(have)}
            <small>{haveN === 1 ? "1 card you own" : `${haveN} cards you own`}</small>
          </span>
          {gapN > 0 && (
            <span className="sum">
              {money(gaps)}
              <small>to fill {gapN === 1 ? "the gap" : `${gapN} gaps`}</small>
            </span>
          )}
          <span className="note">
            {prices.priced} of {prices.asked} priced · TCGplayer market
            {age ? ` · updated ${age}` : ""} · not saved
          </span>
        </>
      )}
    </div>
  );
}

/** "2 hours ago", for a timestamp — a price without its age is a claim. */
function ago(iso) {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 90) return "just now";
  const m = Math.round(s / 60);
  if (m < 90) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 36) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.round(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}
