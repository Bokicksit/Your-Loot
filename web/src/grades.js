// The Goldmine scale, which is what record shops and Discogs price against.
// Stored abbreviated because that's how a grade is written on a sleeve and in
// a listing — a copy is "VG+/VG", never "Very Good Plus/Very Good".
// Shared so the Records page and the Wanted page can't drift apart.
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
