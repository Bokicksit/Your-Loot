import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import useDismiss from "../useDismiss.js";
import EbayLink from "./EbayLink.jsx";
import { Icon } from "./Icons.jsx";
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

export default function CardTile({ card, onChange, onReload }) {
  const [busy, setBusy] = useState(false);
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
      setEntry(null);
      onReload?.();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

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
    <div ref={tileRef} className={`tile ${card.owned.length ? "tile-owned" : ""}`}>
      {card.owned.length > 0 && <span className="owned-badge">×{card.owned.length}</span>}
      {card.image_url ? (
        <img
          src={card.image_url}
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
            <img className="expand-cover" src={card.image_url} alt="" loading="lazy" />
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
              <span className="layer-tag">{o.in_binder ? "Pokédex" : "Box"}</span>
              <span className="game-text">
                <strong>{chipLabel(o)}</strong>
                {o.stamp && <small>{o.stamp} stamp</small>}
              </span>
              <button className="ghost icon" onClick={() => openEdit(o)} title="Edit copy">
                <Icon id="pencil" />
              </button>
            </li>
          ))}
        </ul>
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
