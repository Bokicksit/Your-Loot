import { useEffect } from "react";

/**
 * Put a row's open panels away when the next press lands outside them.
 *
 * Opening a second row counts as pressing outside the first, so rows close
 * themselves and only one stays open — without the page having to track which
 * one that is, and without every row re-rendering when it changes.
 *
 * `guard` gets a veto, and is how a half-typed editor avoids evaporating
 * under a mis-tap.
 */
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

export default function useDismiss(open, close, refs, guard) {
  useEffect(() => {
    if (!open) return undefined;
    const onPress = (e) => {
      // Modals and the photo cropper render through a portal, so they sit
      // outside this row in the DOM while being very much inside it on screen.
      if (e.target.closest?.(".modal-scrim")) return;
      if (refs.some((r) => r.current?.contains(e.target))) return;
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
