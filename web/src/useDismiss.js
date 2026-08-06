import { useEffect } from "react";

/**
 * The standard veto: an editor with changes in it asks before it goes.
 *
 * Tapping slightly off is easy on a phone, and the entry editors hold a screen
 * of typing. Say yes and it closes like anything else; say no and the row is
 * exactly where you left it.
 */
export function keepOpen(vals, initial, open, label) {
  if (!open || !vals || !initial) return false;
  if (JSON.stringify(vals) === JSON.stringify(initial)) return false;
  return !confirm(`Discard your changes to ${label}?`);
}

// Everything that counts as "an item" across the app: a collection row, a card
// and its detail strip, a Pokédex slot and its panel, a wanted-list row.
const ITEM = ".game-row, .tile, .card-detail, .dex-slot, .dex-detail, [data-row]";

/**
 * Close an open panel when you open a different item.
 *
 * Only another item does it. Pressing the background, the toolbar, a filter or
 * a sort menu leaves the panel exactly where it is — closing on any stray tap
 * turned out to be far too eager to live with, and a panel you opened on
 * purpose should not vanish because you reached for the scrollbar.
 *
 * Where each row owns its own state the rows sort this out between
 * themselves, with no page-level bookkeeping and no re-render of the whole
 * list when the open one changes.
 *
 * `inside` is either an array of refs, or a predicate on the pressed element.
 * Lists that track which row is open on the page rather than in the row have
 * nothing to hang a ref on, so they answer the question directly instead.
 *
 * `guard` gets a veto — see keepOpen.
 */
export default function useDismiss(open, close, inside, guard) {
  useEffect(() => {
    if (!open) return undefined;
    const onPress = (e) => {
      // Modals and the photo cropper render through a portal, so they sit
      // outside the row in the DOM while being very much inside it on screen.
      if (e.target.closest?.(".modal-scrim")) return;
      const within =
        typeof inside === "function"
          ? inside(e.target)
          : inside.some((r) => r.current?.contains(e.target));
      if (within) return;
      // the press has to land on some *other* item; anything else is scenery
      if (!e.target.closest?.(ITEM)) return;
      if (guard?.()) return;
      close();
    };
    // pointerdown rather than click, so the panel is already gone by the time
    // whatever you pressed reacts. Capture, so a handler that stops
    // propagation can't strand a panel open.
    document.addEventListener("pointerdown", onPress, true);
    return () => document.removeEventListener("pointerdown", onPress, true);
  });
  // deliberately no dependency array: the listener closes over state that
  // changes on nearly every render, and re-registering it is a couple of
  // microseconds against the stale-closure bugs the array would invite.
}
