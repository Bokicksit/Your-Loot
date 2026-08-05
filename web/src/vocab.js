// Per-copy vocabularies shared between a collection's own page and the Wanted
// page, which both have to offer the same choices. Each entry is
// [stored value, label] — the stored values are frozen, so changing a label
// never rewrites what's already in the database.

// The Goldmine scale, which is what record shops and Discogs price against.
// Stored abbreviated because that's how a grade is written on a sleeve and in
// a listing — a copy is "VG+/VG", never "Very Good Plus/Very Good".
export const VINYL_GRADES = [
  ["M", "Mint"],
  ["NM", "Near Mint"],
  ["VG+", "Very Good Plus"],
  ["VG", "Very Good"],
  ["G+", "Good Plus"],
  ["G", "Good"],
  ["F", "Fair"],
  ["P", "Poor"],
];

// most second-hand vinyl lands here; nobody's shelf is all mint
export const DEFAULT_VINYL_GRADE = "VG";

// What you have of a boxed game, ordered most to least complete. Everything
// down to "Loose" includes the game itself; the last two are spare pieces
// without it. "loose", "CIB" and "sealed" keep their original stored values so
// copies recorded before the list grew still read back correctly.
//
// There's deliberately no "case & manual": having both of those plus the game
// is just CIB, and having both without the game is rare enough to record as
// two spares.
export const GAME_COMPLETENESS = [
  ["sealed", "Sealed"],
  ["CIB", "CIB"],
  ["game+case", "Game & case"],
  ["game+manual", "Game & manual"],
  ["loose", "Loose"],
  ["case only", "Case only"],
  ["manual only", "Manual only"],
];

// Spare pieces — you have part of the release but not the game itself, which
// is why buying one doesn't take the game off your wanted list.
export const GAME_PARTS_ONLY = new Set(["case only", "manual only"]);

/** Display label for a stored value; unrecognised values show as themselves. */
export const labelFor = (pairs, value) =>
  pairs.find(([v]) => v === value)?.[1] ?? value;

/** Keep an off-list stored value selectable so editing a copy can't silently
 *  rewrite it to whichever option happened to be first. */
export const withUnknown = (pairs, value) =>
  !value || pairs.some(([v]) => v === value) ? pairs : [[value, value], ...pairs];
