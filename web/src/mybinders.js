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
 *
 *  Shared and *checked*, though. Fetched once and kept for the life of the
 *  tab, this list quietly went out of date: make a binder, go to your cards,
 *  and the binder you had just made was not among the ones offered — the app
 *  was answering from a list drawn before it existed. So a consumer coming on
 *  screen revalidates one older than STALE, keeps showing what it has while
 *  that lands, and every open list catches up together. The work is one
 *  request however many cards are on the page: callers arriving at once share
 *  the one in flight, which is what made the cache worth having.
 */

const STALE = 20_000;  // ms before a list is worth asking about again

let cache = null;      // the last answer
let fetchedAt = 0;     // when it arrived, for the check above
let inFlight = null;   // so simultaneous callers share one request
const listeners = new Set();

function load() {
  if (inFlight) return inFlight;
  inFlight = api
    .binders()
    .then((rows) => {
      const all = Array.isArray(rows) ? rows : rows?.binders || [];
      cache = all.filter((b) => b.kind === "custom");
      fetchedAt = Date.now();
      listeners.forEach((fn) => fn(cache));
      return cache;
    })
    .catch(() => {
      // An answer we could not get is not an answer that there are none. Keep
      // whatever we had — an empty list here hides every binder somebody owns
      // because one request lost its connection.
      cache = cache || [];
      listeners.forEach((fn) => fn(cache));
      return cache;
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

/** Call after making, renaming or deleting one, so every open list catches up
 *  at once rather than waiting for the staleness check to notice. */
export function refreshBinders() {
  fetchedAt = 0;
  return load();
}

export function useMyBinders() {
  const [binders, setBinders] = useState(cache);

  useEffect(() => {
    listeners.add(setBinders);
    if (cache === null) load();
    else {
      // show what we have straight away, then check it is still true
      setBinders(cache);
      if (Date.now() - fetchedAt > STALE) load();
    }
    return () => listeners.delete(setBinders);
  }, []);

  return binders || [];
}
