# Changelog

Notable changes per tagged release. `VERSION` moves +0.01 on every commit so
that any build traces back to one, but only tagged releases are meant for
pinning — those are the ones listed here.

Full detail is in the commit log, where every change has its own note.

## [Unreleased]

### Added
- **Groundwork for user accounts** (migrations 0018–0021). Nothing signs in
  yet and nothing looks different. A `users` table exists with the current
  owner as user 1; `owned` and `wanted` record who they belong to; `dex_slots`
  and `settings` are keyed per person, so two people can't share one binder or
  overwrite each other's preferences; and `item_override` holds the photo and
  notes you attach to a shared catalogue entry.
- Every `user_id` defaults to the owner in the database, so an existing
  install upgrades with no change in behaviour.

### Fixed
- **`wanted.item_id` was UNIQUE**, which meant exactly one person could ever
  want a given item. Now unique per person.
- **Your photo of an item was written to the shared catalogue row**, where a
  second user would have seen it. Personal art and notes now have their own
  table. Nothing leaked — there has only ever been one user — but it had to be
  fixed before there were two.

### Added
- **Tiles or a list, per collection.** Every collection now has a layout
  toggle next to its sort dropdown. The seven that were rows can draw
  picture-first tiles; Cards, which was always tiles, can draw a detail-first
  list with the thumbnail on the left. Saved per collection, so Movies can be
  tiles while Books stays a list. Defaults reproduce the old layouts exactly.
  The Pokédex is unchanged — it's a picture of a binder. A tile's edit and
  delete controls stay out of the way until you tap it, then appear under the
  picture with the rest of the detail.

- **Book blurbs.** `book_attrs.blurb` already existed, and the expanded book
  panel already rendered it — nothing ever filled it in, so it had always been
  empty. Picking a book now fetches its description from Open Library, the
  same way a game shows its IGDB summary. Coverage is good for well-known
  titles and thin below that; when there's nothing, nothing is shown.

- **Record tracklists.** MusicBrainz gives a track count and nothing else.
  Discogs knows the running order per pressing, which is the level this module
  already tracks records at — a reissue drops a track, a Japanese press has
  Japanese titles. Positions are kept as printed, so "B2" still says which
  side it's on. Migration 0017.
- **Sorting on the wanted list** — last added, first added, A–Z, or grouped by
  collection. Remembered like the other collections'.
- **Sort and filters are remembered per collection.** Choosing "last added",
  or filtering Games to SNES, used to last until you left the page. Stored on
  the server rather than in the browser, so a phone and a desk agree.

### Fixed
- **A typed movie search always looked for the Blu-ray case.** Case art is
  fetched when you pick a film, but the format dropdown comes on the *next*
  step — so the lookup ran against the default and never ran again. Naming the
  format now re-runs it, the way naming a system already does for games. Both
  also stop a previously auto-picked cover from outliving the lookup that
  chose it; a cover you picked yourself is still never replaced. It ordered by
  `wanted.priority`, which nothing has ever set, so every row sat in one NULL
  bucket and fell through to oldest-first. It now defaults to newest-first.
- **The expanded panel was crushed inside a tile.** Opening an item in tile
  view left its details in a 166px column — one word per line of title, a
  summary the width of a ribbon. An opened tile now spans the grid and lays
  itself out as a row for as long as it's open.
- **A manual crop kept the whole photo.** The crop box was positioned in
  percentages of its container, which is full width, while the photo inside it
  is centred and usually narrower — so the rectangle you drew and the pixels
  that got exported were different regions. Measured on a portrait photo: 160px
  of the box covered nothing at all.

### Removed
- **Snap to edges**, which guessed at the item's borders and rarely landed on
  them, and **Whole photo**, which is now simply where the crop box starts.

## [2.02] — 2026-08-07

The first tagged release. Everything before this was development against a
single install; the tags start here so there is something to pin to.

### Removed
- **PSA cert lookup.** PSA never approved the API account, so the endpoint
  answered 403 to everyone and the field on the add sheet was a dead control.
  Grading is unaffected — PSA/BGS/CGC/TAG/ACE and a numeric grade are still
  recorded per copy, typed in by hand.

### Added
- `linux/arm64` images alongside `linux/amd64`, published under one manifest.
  Raspberry Pi, ARM NAS boxes and Apple Silicon can now run it.
- Contribution guide, CLA, security policy and issue templates.

### Fixed
- Box scans for older games missed whenever a shop title and its archive
  filename disagreed about the joining words — *Spider-Man and the X-Men in
  Arcade's Revenge* is filed as *Spider-Man - X-Men - Arcade's Revenge*.
  Measured across 44 titles on eight systems: 34 matched before, 43 now.
- Card tiles at four and five across clipped the card number mid-digit
  (`#44/1(`). The number, set code and rarity now come off the tile at those
  densities, as the copy chips already did, and the expanded card carries all
  three in full.

## Before 2.01

Roughly nine months of development: eight collection types, barcode scanning,
the Pokédex binder, eleven metadata integrations, backup and restore. See
`git log` — commit subjects are written to be read.
