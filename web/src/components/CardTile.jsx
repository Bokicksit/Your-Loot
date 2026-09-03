import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import { useMyBinders } from "../mybinders.js";
import useDismiss from "../useDismiss.js";
import EbayLink from "./EbayLink.jsx";
import { Icon } from "./Icons.jsx";
import { TagChips, TagEditor } from "./Tags.jsx";
import ImagePicker from "./ImagePicker.jsx";
import RarityMark from "./RarityMark.jsx";

const CONDITIONS = ["NM", "LP", "MP", "HP", "DMG"];
const GRADERS = ["Raw", "PSA", "BGS", "CGC", "TAG", "ACE"];
const VARIANTS = ["Non-Holo", "Reverse Holo", "Holo"];
const VARIANT_SHORT = { "Reverse Holo": "RH", Holo: "Holo" };

// A card in the collection grid. Copies are chips ("PSA 9" / "NM") —
// tap a chip to edit in a modal (tiles are too narrow for an inline form),
// + adds another copy. Graded chips are jade, binder chips carry a pokéball.
// Cards you added yourself can be corrected; catalog rows can't, because a
// reseed would overwrite the edit. Same rule the API enforces.
const isYours = (card) => card.source === "manual" || card.source === "tcgdex";

/** The picture currently shown is the card database's own art — nothing the
 *  collector supplied. Photos they upload live on this server under /images/. */
export const isCatalogArt = (card) =>
  card.source === "ptcg" && !(card.image_url || "").startsWith("/images/");

const ENTRY_FIELDS = [
  "title", "national_dex_no", "set_name", "set_abbr",
  "card_number", "set_total", "rarity",
];

export default function CardTile({
  card,
  onChange,
  onReload,
  onTagsChanged,
  // selection mode, driven by the card list — see CardsPage
  selecting = false,
  selected = false,
  onLongPress,
  onToggleSelect,
}) {
  const [busy, setBusy] = useState(false);
  // shared across every tile on the page, fetched once
  const myBinders = useMyBinders();
  const [detailOpen, setDetailOpen] = useState(false); // full-width expansion
  // a card is a tile plus a detail panel below its whole row, not one box, so
  // both count as "inside" — pressing either must not put the panel away
  const tileRef = useRef(null);
  const detailRef = useRef(null);
  useDismiss(detailOpen, () => setDetailOpen(false), [tileRef, detailRef]);
  const [entry, setEntry] = useState(null); // card-detail draft, null = closed
  const [editing, setEditing] = useState(null); // owned id being edited
  const [vals, setVals] = useState({
    condition: "NM",
    grader: "Raw",
    grade: "",
    in_binder: false,
    variant: "Non-Holo",
    stamp: "",
  });

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      const status = await fn();
      onChange(card.id, status);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  // "+" means another one of these, so it copies the last one's condition and
  // print rather than resetting to NM — pulling four of the same common is the
  // case this exists for. Never into the Pokédex though: one card per slot.
  const addCopy = () => {
    const last = card.owned[card.owned.length - 1];
    return run(() =>
      api.addOwned(
        card.id,
        last
          ? {
              condition: last.condition || "NM",
              variant: last.variant,
              stamp: last.stamp,
              grader: last.grader,
              grade: last.grade,
              in_binder: false,
            }
          : { condition: "NM" }
      )
    );
  };

  const removeLastCopy = () => {
    const last = card.owned[card.owned.length - 1];
    if (last) removeCopy(last);
  };

  // Two copies with the same grade, print, stamp and slot are indistinguishable,
  // so they read as one line with a count rather than a stack of identical
  // chips. Anything that differs still gets its own chip — that's the whole
  // point of tracking copies separately.
  const copyGroups = card.owned.reduce((acc, o) => {
    const key = [o.condition, o.variant, o.stamp, o.grader, o.grade, o.in_binder]
      .map((v) => v ?? "")
      .join("|");
    const found = acc.find((g) => g.key === key);
    if (found) found.copies.push(o);
    else acc.push({ key, copies: [o] });
    return acc;
  }, []);
  const removeCopy = (o) => {
    const last = card.owned.length === 1;
    if (
      !confirm(
        `Remove ${card.title} (${chipLabel(o)})?` +
          (last ? " This is your last copy — it leaves the collection." : "")
      )
    )
      return;
    run(() => api.removeOwned(card.id, o.id));
  };

  const openEntry = () => {
    const a = card.attrs;
    setEntry({
      title: card.title || "",
      national_dex_no: a.national_dex_no ?? "",
      set_name: a.set_name || "",
      set_abbr: a.set_abbr || "",
      card_number: a.card_number || "",
      set_total: a.set_total ?? "",
      rarity: a.rarity || "",
      tags: card.tags || [],
    });
  };

  const saveEntry = async () => {
    if (busy) return;
    if (!entry.title.trim()) {
      alert("A card needs a name.");
      return;
    }
    setBusy(true);
    try {
      await api.updateCard(card.id, {
        title: entry.title.trim(),
        set_name: entry.set_name.trim() || null,
        set_abbr: entry.set_abbr.trim() || null,
        card_number: entry.card_number.trim() || null,
        rarity: entry.rarity.trim() || null,
        // numeric fields: blank clears them rather than storing 0
        national_dex_no: entry.national_dex_no ? Number(entry.national_dex_no) : null,
        set_total: entry.set_total ? Number(entry.set_total) : null,
      });
      // Staged with the rest of the form, so Cancel discards a tag the
      // same way it discards a retyped rarity.
      await api.setItemTags(card.id, "cards", entry.tags);
      onTagsChanged?.();
      setEntry(null);
      onReload?.();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  /* Long press to start selecting, then tap to add to the selection.
   *
   * Half a second, and cancelled by moving — on a phone the card list is
   * something you scroll, and a press that becomes a selection because your
   * thumb rested a moment too long is worse than no gesture at all. A right
   * click does the same thing with a mouse, where there is no long press.
   *
   * Only cards you actually own can be selected: filing works on a copy, and
   * a card you do not own has none.
   */
  const pressTimer = useRef(null);
  const pressed = useRef(false);
  const selectable = card.owned.length > 0;

  const cancelPress = () => {
    clearTimeout(pressTimer.current);
    pressTimer.current = null;
  };

  const pressHandlers = !selectable
    ? {}
    : {
        onPointerDown: (e) => {
          if (e.pointerType === "mouse" && e.button !== 0) return;
          pressed.current = false;
          cancelPress();
          pressTimer.current = setTimeout(() => {
            pressed.current = true;
            onLongPress?.(card);
          }, 500);
        },
        onPointerUp: cancelPress,
        onPointerLeave: cancelPress,
        onPointerCancel: cancelPress,
        onPointerMove: cancelPress,
        onContextMenu: (e) => {
          if (!selecting) {
            e.preventDefault();
            onLongPress?.(card);
          }
        },
        // In selection mode the whole tile is one big checkbox, so it has to
        // swallow the clicks that would otherwise open the detail panel.
        onClickCapture: (e) => {
          if (!selecting) return;
          e.preventDefault();
          e.stopPropagation();
          onToggleSelect?.(card);
        },
      };

  // The copy being edited, and the binders it is or isn't already on. Split
  // here rather than in the markup so the two lists cannot disagree.
  const editingCopy = card.owned.find((o) => o.id === editing);
  const filedIn = new Set(editingCopy?.binder_ids || []);
  const inBinders = myBinders.filter((b) => filedIn.has(b.id));
  const notInBinders = myBinders.filter((b) => !filedIn.has(b.id));

  /** Put this copy on a shelf, or take it off. */
  const fileCopy = (binderId, add) =>
    run(async () => {
      if (add) await api.binderAddCards(binderId, [editing]);
      else await api.binderRemoveCard(binderId, editing);
      // the copy's binder_ids come from the server, so the list has to come
      // back before the chips can be right
      onReload?.();
    });

  const openEdit = (o) => {
    setEditing(o.id);
    setVals({
      condition: o.condition || "NM",
      grader: o.grader || "Raw",
      grade: o.grade || "",
      in_binder: o.in_binder,
      variant: o.variant || "Non-Holo",
      stamp: o.stamp || "",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const graded = vals.grader !== "Raw";
      const status = await api.updateOwned(card.id, editing, {
        condition: vals.condition,
        grader: graded ? vals.grader : null,
        grade: graded && vals.grade ? vals.grade : null,
        in_binder: vals.in_binder && !!card.attrs.national_dex_no,
        variant: vals.variant === "Non-Holo" ? null : vals.variant,
        stamp: vals.stamp.trim() || null,
      });
      setEditing(null);
      return status;
    });

  const chipLabel = (o) =>
    [
      VARIANT_SHORT[o.variant],
      o.grader ? `${o.grader} ${o.grade || "?"}` : o.condition,
      o.stamp && "stamped",
    ]
      .filter(Boolean)
      .join(" · ") || "set condition…";

  const a = card.attrs;
  // tile stays terse: the printed set code, full name lives in the expansion
  const shortSet = a.set_abbr || a.set_name;
  const numLine = `#${a.card_number}${a.set_total ? `/${a.set_total}` : ""}`;
  const setLine = `${a.set_name} ${numLine}`;

  const editingGroup = copyGroups.find((g) => g.copies.some((c) => c.id === editing));

  const editorModal = (
    <div className="modal-scrim" onClick={() => setEditing(null)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Edit copy</h2>
        <p>
          {card.title} · {setLine}
        </p>
        {/* the chip stands for several identical copies, so be explicit that
            this changes one of them and splits it onto its own line */}
        {editingGroup && editingGroup.copies.length > 1 && (
          <p className="modal-note">
            <Icon id="info" />
            You have {editingGroup.copies.length} of these. This edits one; the
            rest stay as they are.
          </p>
        )}
        <div className="form-row" style={{ width: "100%" }}>
          <select
            value={vals.condition}
            onChange={(e) => setVals({ ...vals, condition: e.target.value })}
          >
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <select
            value={vals.grader}
            onChange={(e) => setVals({ ...vals, grader: e.target.value })}
          >
            {GRADERS.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
          <input
            type="text"
            inputMode="decimal"
            placeholder="9.5"
            style={{ maxWidth: "80px" }}
            disabled={vals.grader === "Raw"}
            value={vals.grade}
            onChange={(e) => setVals({ ...vals, grade: e.target.value })}
          />
        </div>
        <div className="form-row" style={{ width: "100%" }}>
          <select
            value={vals.variant}
            onChange={(e) => setVals({ ...vals, variant: e.target.value })}
          >
            {VARIANTS.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <input
            type="text"
            className="grow"
            placeholder="Stamp (Mega Evolution…)"
            value={vals.stamp}
            onChange={(e) => setVals({ ...vals, stamp: e.target.value })}
          />
        </div>
        {card.attrs.national_dex_no && (
          <button
            type="button"
            className={`toggle ${vals.in_binder ? "on" : ""}`}
            onClick={() => setVals({ ...vals, in_binder: !vals.in_binder })}
          >
            In the Pokédex
          </button>
        )}

        {/* Where this copy lives, and where it could. Separate from the
            Pokédex switch above on purpose: that one picks a favourite among
            the copies you own, this one puts a copy on a shelf, and they are
            not the same question. Applied immediately rather than on save —
            filing is its own act, and a card that moved should look moved. */}
        {myBinders.length > 0 && (
          <div className="binder-pick">
            {inBinders.map((b) => (
              <span key={b.id} className="chip binder-chip">
                <Icon id="card" />
                {b.name}
                <button
                  type="button"
                  title={`Take it out of ${b.name}`}
                  disabled={busy}
                  onClick={() => fileCopy(b.id, false)}
                >
                  ×
                </button>
              </span>
            ))}
            {notInBinders.length > 0 && (
              <select
                value=""
                disabled={busy}
                onChange={(e) => e.target.value && fileCopy(Number(e.target.value), true)}
              >
                <option value="">Add to a binder…</option>
                {notInBinders.map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
            )}
          </div>
        )}
        <div className="form-row" style={{ width: "100%" }}>
          <button
            className="primary"
            style={{ flex: 1 }}
            onClick={saveEdit}
            disabled={busy}
          >
            <Icon id="check" />
            Save
          </button>
          <button className="ghost" onClick={() => setEditing(null)}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
    <div
      ref={tileRef}
      className={`tile ${card.owned.length ? "tile-owned" : ""} ${
        selecting ? "tile-selecting" : ""
      } ${selected ? "tile-selected" : ""}`}
      {...pressHandlers}
    >
      {selecting && (
        <span className={`tile-check ${selected ? "on" : ""}`} aria-hidden="true">
          <Icon id="check" />
        </span>
      )}
      {card.owned.length > 0 && (
        <span className={`owned-badge ${card.owned.length > 1 ? "many" : ""}`}>
          ×{card.owned.length}
        </span>
      )}
      {card.image_url ? (
        <img
          src={card.image_url} data-item={card.id}
          alt={card.title}
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={() => setDetailOpen(!detailOpen)}
        />
      ) : (
        <div
          className="placeholder"
          data-label={card.title}
          style={{ cursor: "pointer" }}
          onClick={() => setDetailOpen(!detailOpen)}
        />
      )}
      <div className="tile-info">
        <strong style={{ cursor: "pointer" }} onClick={() => setDetailOpen(!detailOpen)}>
          {card.title}
        </strong>
        <small style={{ cursor: "pointer" }} onClick={() => setDetailOpen(!detailOpen)}>
          <RarityMark rarity={a.rarity} />
          <span className="set-abbr">{shortSet}</span> {numLine}
        </small>
        <span className="copy-chips">
          {copyGroups.map((g) => {
            const o = g.copies[0];
            const n = g.copies.length;
            return (
              <span
                key={g.key}
                className={`chip copy ${o.grader ? "graded" : ""}`}
                onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
                title={n > 1 ? `Edit one of these ${n}` : "Edit this copy"}
              >
                {o.in_binder && <Icon id="ball" />}
                {o.in_custom && <Icon id="binder" />}
                {chipLabel(o)}
                {n > 1 && <em className="chip-mult">×{n}</em>}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    // take the newest of the identical ones — they're the same
                    // object as far as the collection is concerned
                    removeCopy(g.copies[n - 1]);
                  }}
                  title={n > 1 ? "Remove one of these" : "Remove this copy"}
                >
                  <Icon id="x" />
                </button>
              </span>
            );
          })}
          {/* how many of this card you have, and the quickest way to change it */}
          <span className="copy-step">
            <button
              onClick={removeLastCopy}
              disabled={busy || !card.owned.length}
              title="Remove a copy"
            >
              <Icon id="minus" />
            </button>
            <b>{card.owned.length}</b>
            <button onClick={addCopy} disabled={busy} title="Add another copy">
              <Icon id="plus" />
            </button>
          </span>
        </span>
      </div>
      {editing !== null && createPortal(editorModal, document.body)}
    </div>
    {detailOpen && (
      <div ref={detailRef} className="dex-detail card-detail">
        <div className="expand-card">
          {card.image_url && (
            <img className="expand-cover" src={card.image_url} data-item={card.id} alt="" loading="lazy" />
          )}
          <div className="expand-body">
            <span className="expand-title">{card.title}</span>
            <span className="expand-sub">
              {a.set_name}
              {a.set_abbr ? ` (${a.set_abbr})` : ""}
              {a.set_year ? ` · ${a.set_year}` : ""}
            </span>
            <span className="game-info-line">
              <RarityMark rarity={a.rarity} /> {a.rarity || "—"} · Card {numLine}
              {a.national_dex_no ? ` · Dex #${a.national_dex_no}` : ""}
            </span>
          </div>
          {/* sellers title a card by its number and set, never by its rarity */}
          <EbayLink
            title={card.title}
            terms={[
              `${a.card_number}${a.set_total ? `/${a.set_total}` : ""}`,
              a.set_name,
            ]}
          />
        </div>
        <ul>
          {card.owned.map((o) => (
            <li key={o.id}>
              <span className="layer-tag">{whereFiled(o)}</span>
              <span className="game-text">
                <strong>{chipLabel(o)}</strong>
                {o.stamp && <small>{o.stamp} stamp</small>}
              </span>
              <CopyBinders copy={o} onChange={onReload} />
              <button className="ghost icon" onClick={() => openEdit(o)} title="Edit copy">
                <Icon id="pencil" />
              </button>
            </li>
          ))}
        </ul>
        <TagChips tags={card.tags} />
        {/* the tile hides its chips once the grid gets dense, so the counter
            has to exist somewhere that isn't the tile */}
        <div className="form-row">
          <span className="copy-step">
            <button onClick={removeLastCopy} disabled={busy || !card.owned.length} title="Remove a copy">
              <Icon id="minus" />
            </button>
            <b>{card.owned.length}</b>
            <button onClick={addCopy} disabled={busy} title="Add another copy">
              <Icon id="plus" />
            </button>
          </span>
        </div>
        <div className="form-row wrap">
          {/* every card can get its own art — a photo of your actual copy, or
              a pasted link when the catalog has none */}
          <ImagePicker
            value={card.image_url}
            label={card.image_url ? "Photo" : "Add photo"}
            // On a catalog card the picture is the reference art, not
            // something you added — offering to delete it only invites the
            // accident. Once you've put your own photo on, ✕ takes yours off.
            removable={!isCatalogArt(card)}
            removeHint={
              card.source === "ptcg"
                ? "The catalog picture returns the next time the card database refreshes."
                : undefined
            }
            onChange={async (url) => {
              try {
                await api.updateCard(card.id, { image_url: url });
                onReload?.();
              } catch (e) {
                alert(e.message);
              }
            }}
          />
          {isYours(card) ? (
            <>
              <button
                className="ghost"
                style={{ marginLeft: "auto" }}
                title="Correct this card's details"
                onClick={() => (entry ? setEntry(null) : openEntry())}
              >
                <Icon id="pencil" />
                Edit card
              </button>
              <button
                className="ghost danger icon"
                title="Delete this card entry"
                onClick={async () => {
                  if (!confirm(`Delete the card entry "${card.title}"?`)) return;
                  try {
                    await api.deleteCard(card.id);
                    onReload?.();
                  } catch (e) {
                    alert(e.message);
                  }
                }}
              >
                <Icon id="trash" />
              </button>
            </>
          ) : (
            // No delete or edit here, and the absence looked like a bug — say
            // why. Dump rows are shared reference data that a reseed rewrites,
            // so what the user actually wants is to drop their copies.
            <span className="catalog-note">
              <Icon id="info" />
              <span>
                This is a <strong>catalog card</strong>, shared by every collection —
                its details can't be edited and it can't be deleted. Remove your
                copies above and it leaves your collection but stays searchable.
              </span>
            </span>
          )}
        </div>

        {entry && (
          <div className="entry-edit">
            <span className="game-info-line">Card details</span>
            <div className="form-row">
              <input
                type="text"
                className="grow"
                placeholder="Card name"
                value={entry.title}
                onChange={(e) => setEntry({ ...entry, title: e.target.value })}
              />
              <input
                type="text"
                style={{ maxWidth: "110px" }}
                placeholder="Dex #"
                inputMode="numeric"
                value={entry.national_dex_no}
                onChange={(e) => setEntry({ ...entry, national_dex_no: e.target.value })}
              />
            </div>
            <div className="form-row">
              <input
                type="text"
                className="grow"
                placeholder="Set name"
                value={entry.set_name}
                onChange={(e) => setEntry({ ...entry, set_name: e.target.value })}
              />
              <input
                type="text"
                style={{ maxWidth: "90px" }}
                placeholder="Code"
                value={entry.set_abbr}
                onChange={(e) => setEntry({ ...entry, set_abbr: e.target.value })}
              />
            </div>
            <div className="form-row">
              <input
                type="text"
                style={{ maxWidth: "110px" }}
                placeholder="Number"
                value={entry.card_number}
                onChange={(e) => setEntry({ ...entry, card_number: e.target.value })}
              />
              <input
                type="text"
                style={{ maxWidth: "100px" }}
                placeholder="of total"
                inputMode="numeric"
                value={entry.set_total}
                onChange={(e) => setEntry({ ...entry, set_total: e.target.value })}
              />
              <input
                type="text"
                className="grow"
                placeholder="Rarity"
                value={entry.rarity}
                onChange={(e) => setEntry({ ...entry, rarity: e.target.value })}
              />
            </div>
            <div className="form-row">
              <TagEditor
                scope="cards"
                id={card.id}
                value={entry.tags}
                onChange={(tags) => setEntry({ ...entry, tags })}
              />
            </div>
            <div className="form-row">
              <button className="primary" onClick={saveEntry} disabled={busy}>
                <Icon id="check" />
                {busy ? "Saving…" : "Save"}
              </button>
              <button className="ghost" onClick={() => setEntry(null)}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    )}
    </>
  );
}

/** Which of your binders this copy is in, and a way to change it.
 *
 *  Here rather than only on the binder page because the thought usually
 *  arrives the other way round: you are looking at a card and realise it
 *  belongs in the Trades binder. Filing it in one does not take it out of any
 *  other — that is the point of the whole feature — so this is a set of
 *  toggles rather than a choice of one.
 *
 *  Set binders are not offered. Owning the card is what fills a slot there,
 *  so there is nothing to put in by hand.
 */
/** Where a copy is kept, as the row says it. A copy can be in the Pokédex
 *  and in a binder of your own at the same time — the same card, filed in two
 *  places — and the old label picked one and hid the other. */
function whereFiled(o) {
  if (o.in_binder && o.in_custom) return "Pokédex · Binder";
  if (o.in_binder) return "Pokédex";
  if (o.in_custom) return "Binder";
  return "Box";
}

function CopyBinders({ copy, onChange }) {
  const [open, setOpen] = useState(false);
  const [shelf, setShelf] = useState(null);
  const [busy, setBusy] = useState(null);
  const inIt = new Set(copy.binder_ids || []);

  useEffect(() => {
    if (open && shelf === null) {
      api.binders().then((d) => setShelf(d.binders.filter((b) => b.kind === "custom")));
    }
  }, [open, shelf]);

  const toggle = async (b) => {
    setBusy(b.id);
    try {
      if (inIt.has(b.id)) await api.binderRemoveCard(b.id, copy.id);
      else await api.binderAddCards(b.id, [copy.id]);
      onChange?.();
    } finally {
      setBusy(null);
    }
  };

  return (
    <span className="copy-binders">
      <button
        className={`ghost icon ${inIt.size ? "on" : ""}`}
        onClick={() => setOpen(!open)}
        title={inIt.size ? `In ${inIt.size} binder${inIt.size === 1 ? "" : "s"}` : "Put in a binder"}
      >
        <Icon id="card" />
        {inIt.size > 0 && <em className="chip-mult">{inIt.size}</em>}
      </button>
      {open && (
        <span className="binder-menu">
          {shelf === null && <small>Loading…</small>}
          {shelf?.length === 0 && <small>No binders of your own yet.</small>}
          {(shelf || []).map((b) => (
            <button
              key={b.id}
              className={`toggle ${inIt.has(b.id) ? "on" : ""}`}
              disabled={busy === b.id}
              onClick={() => toggle(b)}
            >
              {b.name}
            </button>
          ))}
        </span>
      )}
    </span>
  );
}
