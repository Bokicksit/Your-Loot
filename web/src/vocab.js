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
// down to "Loose" includes the game itself; the last three are spare pieces
// without it — "Case & manual" is an empty box with its manual, not a complete
// copy (that's CIB). "loose", "CIB" and "sealed" keep their original stored
// values so copies recorded before the list grew still read back correctly.
export const GAME_COMPLETENESS = [
  ["sealed", "Sealed"],
  ["CIB", "CIB"],
  ["game+case", "Game & case"],
  ["game+manual", "Game & manual"],
  ["loose", "Loose"],
  ["case+manual", "Case & manual (no game)", "Case & manual"],
  ["case only", "Case only"],
  ["manual only", "Manual only"],
];

// Spare pieces — you have part of the release but not the game itself, which
// is why buying one doesn't take the game off your wanted list.
export const GAME_PARTS_ONLY = new Set(["case+manual", "case only", "manual only"]);

// A LEGO set is bought sealed and then usually stops being sealed, so what a
// copy is worth turns on how much of it survived: box, instructions, and
// whether the bricks are all there.
// third element is the badge form — see shortFor()
export const LEGO_COMPLETENESS = [
  ["sealed", "Sealed (MISB)", "MISB"],
  ["complete+box", "Complete, box & instructions", "CIB"],
  ["complete+instructions", "Complete with instructions, no box", "No box"],
  ["complete", "Complete, bricks only", "Bricks only"],
  ["incomplete", "Missing pieces", "Missing pcs"],
  ["parts", "Parts only", "Parts"],
  ["instructions", "Instructions only", "Instr. only"],
  ["box", "Box only", "Box only"],
];

// Same idea as GAME_PARTS_ONLY: an empty box or a spare instruction booklet
// isn't the set, so it doesn't end the hunt.
export const LEGO_PARTS_ONLY = new Set(["parts", "instructions", "box"]);

export const LEGO_CONDITION = [
  ["new", "New"],
  ["like-new", "Like new"],
  ["used", "Used"],
  ["worn", "Worn"],
  ["damaged", "Damaged"],
];

// Raw comics are graded on this scale; a slabbed one carries the grader's
// number instead (CGC 9.8), which reuses the same grader/grade columns cards
// already have.
export const COMIC_GRADES = [
  ["MT", "Mint"],
  ["NM", "Near Mint"],
  ["VF", "Very Fine"],
  ["FN", "Fine"],
  ["VG", "Very Good"],
  ["GD", "Good"],
  ["FR", "Fair"],
  ["PR", "Poor"],
];

export const COMIC_GRADERS = ["CGC", "CBCS", "PGX", "EGS"];
// the 10-point scale a slab is labelled with
export const COMIC_SLAB_GRADES = [
  "10.0", "9.9", "9.8", "9.6", "9.4", "9.2", "9.0", "8.5", "8.0", "7.5",
  "7.0", "6.5", "6.0", "5.5", "5.0", "4.5", "4.0", "3.5", "3.0", "2.5",
  "2.0", "1.8", "1.5", "1.0", "0.5",
];

/** Display label for a stored value; unrecognised values show as themselves. */
export const labelFor = (pairs, value) =>
  pairs.find(([v]) => v === value)?.[1] ?? value;

/** The badge form. A dropdown has a whole line to explain itself; a chip sits
 *  inline in a row next to the title and has to stay short, so entries carry
 *  an optional third element for it. Falls back to the full label. */
export const shortFor = (pairs, value) => {
  const hit = pairs.find(([v]) => v === value);
  return hit ? hit[2] ?? hit[1] : value;
};

/** Keep an off-list stored value selectable so editing a copy can't silently
 *  rewrite it to whichever option happened to be first. */
export const withUnknown = (pairs, value) =>
  !value || pairs.some(([v]) => v === value) ? pairs : [[value, value], ...pairs];
