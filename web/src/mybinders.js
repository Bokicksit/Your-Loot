import { useEffect, useState } from "react";
import { api } from "./api.js";

/** The binders a card can actually be put into, fetched once.
 *
 *  Custom ones only, and that is not a simplification. A set binder's slots
 *  belong to specific cards — you fill it by owning the right one, not by
 *  choosing — and the Pokédex fills by picking a favourite among the copies
 *  you have, which is its own toggle. Only a custom binder is a shelf you
 *  arrange by hand, so only a custom binder can be offered in a list that
 *  says "put this here".
 *
 *  Shared rather than per-component: a page of a hundred cards would
 *  otherwise ask for the same list a hundred times.
 */

let cache = null;      // the last answer
let inFlight = null;   // so simultaneous callers share one request
const listeners = new Set();

function load() {
  if (inFlight) return inFlight;
  inFlight = api
    .binders()
    .then((rows) => {
      const all = Array.isArray(rows) ? rows : rows?.binders || [];
      cache = all.filter((b) => b.kind === "custom");
      listeners.forEach((fn) => fn(cache));
      return cache;
    })
    .catch(() => {
      cache = [];
      listeners.forEach((fn) => fn(cache));
      return cache;
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

/** Call after making, renaming or deleting one, so every open list catches up. */
export function refreshBinders() {
  cache = null;
  return load();
}

export function useMyBinders() {
  const [binders, setBinders] = useState(cache);

  useEffect(() => {
    listeners.add(setBinders);
    if (cache === null) load();
    else setBinders(cache);
    return () => listeners.delete(setBinders);
  }, []);

  return binders || [];
}
