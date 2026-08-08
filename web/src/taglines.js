/* The line above the collections.
 *
 * It was "What are we opening?" and nothing else, which is a good line and
 * still the first one here — it just doesn't need to be the only one for the
 * next several years.
 *
 * Category lines only join the pool when you actually collect that category,
 * so a record collector is never asked about minifigs and somebody who only
 * does cards isn't asked about pressings. Turn all eight on and the pool is
 * 162 lines; turn one on and it's 64.
 */

export const GENERAL = [
  // opening things
  "What are we opening?",
  "Which box are we opening?",
  "What did you bring home?",
  "What landed this week?",
  "Something new, or old favourites?",
  "Sealed, or shall we look?",
  "What's still in the bag?",
  // the shelf
  "Which shelf are we raiding?",
  "What's new on the shelf?",
  "Which shelf are we proud of?",
  "Which shelf needs attention?",
  "Which shelf first?",
  "Back to the shelves.",
  "What's earned its spot?",
  // admiring
  "What are we admiring today?",
  "Just here to look at it again?",
  "Back for another look?",
  "Caught them all yet?",
  "Show me the good stuff.",
  "What are we showing off?",
  "Time to admire the haul?",
  "Which one's the favourite today?",
  // the hunt
  "What are we hunting today?",
  "What are we chasing today?",
  "Which gap are we filling?",
  "Anything still missing?",
  "Still one short?",
  "Which run are we chasing?",
  "What are we after?",
  "Who's still missing?",
  // piles and stacks
  "Which pile are we starting with?",
  "Which stack are we tackling?",
  "Pick a pile.",
  "What are we stacking today?",
  "What's on the pile today?",
  "How's the dex looking?",
  // sorting and filing
  "What are we sorting today?",
  "What are we cataloguing?",
  "What are we filing today?",
  "Anything new to log?",
  "Sleeved and sorted?",
  "What are we counting today?",
  // digging about
  "Where are we digging today?",
  "Up for a dig?",
  "Which crate are we flipping through?",
  "Where's the good stuff hiding?",
  "What's caught your eye?",
  // the hoard
  "Still hunting shinies?",
  "Anything to add to the hoard?",
  "Here for the whole lot?",
];

export const BY_MODULE = {
  cards: [
    "What did you pull?",
    "Any good pulls today?",
    "Caught them all yet?",
    "How's the dex looking?",
    "Still hunting shinies?",
    "Who's still missing?",
    "Any gaps in the binder?",
    "Sleeved and sorted?",
    "Which set are we finishing?",
    "Chasing a secret rare?",
    "Anything worth grading?",
    "How many doubles now?",
    "Which page needs filling?",
    "Pulled anything ridiculous?",
  ],
  games: [
    "Which cart are we hunting?",
    "Boxed, or loose and loved?",
    "Complete in box?",
    "Which system today?",
    "Found a manual at last?",
    "What's still sealed?",
    "Which shelf of carts?",
    "Any flea market finds?",
    "Anything with the inserts?",
    "Which region are we after?",
    "What came home this week?",
    "Still missing the box?",
    "Which console's calling?",
    "Cart or disc today?",
  ],
  hardware: [
    "Which console today?",
    "Anything still boxed?",
    "Does it still power on?",
    "Counting controllers again?",
    "All the cables accounted for?",
    "Which system are we hunting?",
    "Boxed, or bare?",
    "Which shelf of consoles?",
    "Found the right power brick?",
    "Working, or one for parts?",
    "Which model number?",
    "Original, or the revision?",
    "Anything still sealed?",
    "Which one needs a recap?",
  ],
  movies: [
    "Which case are we opening?",
    "Steelbook or standard?",
    "What's still in shrink?",
    "Which edition did you get?",
    "4K, or is Blu-ray fine?",
    "Anything with the slipcover?",
    "Which box set today?",
    "Found the special edition?",
    "What's the region on that?",
    "Which shelf of discs?",
    "Still chasing a steelbook?",
    "Did the package finally come?",
    "Which cut is it?",
    "Any thrift store bargains?",
  ],
  books: [
    "Which spine caught your eye?",
    "First edition, or a reader?",
    "Hardback or paperback?",
    "Is the jacket intact?",
    "Which shelf are we filling?",
    "Found the matching edition?",
    "Any thrift store finds?",
    "Which series are we completing?",
    "Signed, or just well read?",
    "What's still to shelve?",
    "Which author today?",
    "Any first printings?",
    "Which gap on the shelf?",
    "What did the shop have?",
  ],
  records: [
    "Which crate are we in?",
    "Original press or reissue?",
    "How's the sleeve looking?",
    "What's the catalogue number?",
    "Any thrift store wax?",
    "Which pressing did you get?",
    "Still sealed, or spun?",
    "Which label today?",
    "Found it on vinyl at last?",
    "Media or sleeve grade?",
    "What's worth a spin?",
    "Which crate needs digging?",
    "First press, or good enough?",
    "What came out of the bins?",
  ],
  lego: [
    "Sealed, or built?",
    "Which set are we after?",
    "All the minifigs there?",
    "Are the instructions in it?",
    "How many pieces this time?",
    "Which theme today?",
    "Anything still shrink-wrapped?",
    "Bricks only, or complete?",
    "Which set number?",
    "Found the missing minifig?",
    "Still in the box?",
    "What's on the build pile?",
    "Retired, or still in shops?",
    "Which shelf of sets?",
  ],
  comics: [
    "Which issue are we after?",
    "Bagged and boarded?",
    "Which run are we completing?",
    "Variant, or the standard cover?",
    "Slabbed, or raw?",
    "Which longbox today?",
    "Found the key issue?",
    "What's the grade on that?",
    "Which volume is it?",
    "Anything from the quarter bin?",
    "First appearance?",
    "Which shelf of long boxes?",
    "Newsstand or direct?",
    "What's still on the pull list?",
  ],
};

// The first general line. Used until settings load, so the heading never
// starts as one line and swaps to another in front of you.
export const DEFAULT_TAGLINE = GENERAL[0];

const KEY = "loot.tagline";

/** One line per visit.
 *
 *  Held in sessionStorage rather than picked on render: a heading that changes
 *  every time you tap back to Collections reads as a bug, not as charm. A new
 *  tab or a new day gets a new one.
 */
export function pickTagline(enabledKeys) {
  try {
    const kept = sessionStorage.getItem(KEY);
    if (kept) return kept;
  } catch {
    /* private browsing, embedded webviews — a tagline is not worth failing over */
  }
  // Deduped: a handful of lines are good enough to sit in both the general
  // list and a category's, and without this a cards collector would get those
  // five at twice the odds of everything else for no reason anyone chose.
  const pool = [
    ...new Set(
      GENERAL.concat((enabledKeys || []).flatMap((k) => BY_MODULE[k] || []))
    ),
  ];
  const pick = pool[Math.floor(Math.random() * pool.length)];
  try {
    sessionStorage.setItem(KEY, pick);
  } catch {
    /* as above */
  }
  return pick;
}
