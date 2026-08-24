# Changelog

Notable changes per tagged release. `VERSION` moves +0.01 on every commit so
that any build traces back to one, but only tagged releases are meant for
pinning — those are the ones listed here.

Full detail is in the commit log, where every change has its own note.

## [Unreleased]

### Fixed
- **The address follows the room.** Arriving at `/u/bo/pokedex` and then
  backing out left the bar still saying "pokedex" while you looked at games
  or at the room — so copying it handed somebody a link to a different page
  than the one on screen. Opening a shelf, opening a binder, and closing
  back to the room each rewrite the address now, and copying it at any point
  reproduces exactly what you are looking at. The address a link arrived
  with is left alone, since `/binders` and `/cards` open the same layer and
  rewriting one into the other under somebody who just followed a link would
  answer a question they did not ask. It replaces rather than pushes: back
  still means "wherever I came from", not a walk out through every shelf.
- **amiibo kept their details through an export.** The import side always
  knew how to rebuild a figure; the export side never listed
  `amiibo_attrs`, so every figure left as `attrs: null` and came back from a
  restore as a bare title — no character, series or type. Hand-typed figures
  were the ones that actually lost data, since a catalogue pick is found
  again by its id whatever the file says.
- **amiibo and hardware joined the tenancy sweep.** The cross-account test
  covered seven collections and skipped those two, so their read filters and
  the v3.57 write guard were never exercised. Hardware needed the sweep most:
  it is the games module with a flag, and a shelf one flag away from another
  is exactly the one a filter forgets.
- **The room's shelves actually fill now.** Book, game and film spines in
  the collector's room had no height, so a seventeen-book case drew as empty
  furniture. Each spine now sizes itself from its own title — hashed like
  its colour, so the shelf is stable between visits — and the games unit's
  rows gained the height they stand in.
- **Editing and deleting an entry now checks whose it is.** On a multi-user
  install, the write endpoints took any item id — one account could rewrite
  or cascade-delete another's shelf. One guard now covers all eight
  collections: touching a shared row needs a stake in it (your copy or your
  want), and a delete refuses while somebody else still holds the row. A
  single-user install is unaffected — the owner is the admin, and admins
  pass. Found in a security audit; covered by new tenancy tests.

### Changed
- **The tagline sits on the things it describes.** "Build the binder. Send
  the link." has left the hero, where it promised both halves to somebody
  who did not yet know what a binder was for. "Build the binder." now hangs
  over the Pokédex and "Send the link." over the collector's room, so each
  lands on the section that earns it.
- **The front page leads with the shelves.** What it keeps comes first now,
  the two ways in sit under it once that question is answered, and the
  Pokédex has its own section below rather than sharing the hero. The dex
  wall fills from its own travel through the screen at every width, since
  it is below the fold at all of them now.

### Added
- **The card scanner watches, and carries a light.** No capture button to
  press: hold the card in the outline and a frame goes quietly to the server
  about once a second, and when the same card comes back top twice running —
  the barcode scanner's own rule, because one blurry frame can match a
  neighbour and two in a row cannot — it locks, buzzes, and moves to the
  pick. "Identify now" stays as the manual override and is the only path
  that says "nothing matched" out loud. Phones with a torch get the same
  light button the barcode scanner has, for the card angled under a lamp.
- **The scanner keeps itself current.** `HASH_CARD_ART=true` and every start
  fingerprints whatever card art is new, in the background — so a freshly
  seeded set becomes scannable without anybody remembering a command, and a
  catalogue with nothing new costs one database question. Off by default:
  the first run is twenty thousand fetches, and that is a thing to choose.
  (Also declared `CARD_ART` in the compose files, which documented it
  without ever passing it to the container.)
- **Point the camera at a card.** Cards carry no barcode, so the scanner
  reads the picture instead: every card's artwork is reduced to sixty-four
  bits describing what it looks like, and a frame from the camera is matched
  against the catalogue by how many of those bits disagree. No key, no
  quota, no request leaving the server — the only lookup here that costs
  nothing to ask. It offers a few candidates rather than picking one,
  because a fingerprint sees artwork and a reverse holo is the same picture
  as the normal print; which printing you own is a question about your copy,
  and you can see the answer. Migration 0051 adds the column;
  `seed/hash_cards.py` fills it in once, and until it has run the scanner
  finds nothing and says so.
- **A link straight to one shelf.** `/u/bo/games`, `/u/bo/records`,
  `/u/bo/pokedex` — the same public page, arriving with that collection
  already open, so a link can be about the one thing somebody collects
  rather than about everything they own. Cards get two extra addresses of
  their own: `/pokedex` opens the dex itself, `/binders` the shelf of them.
  Settings lists every address that answers, ready to copy, and the list is
  built by the server from the same rules the routes enforce — so it can
  never offer a link that 404s. Supporter-only, because the room is what
  these open into; a free profile has no layer to open and says so with a
  404 rather than quietly showing the whole page instead.
- **Reserved names, for the operator.** The admin panel can set a screen
  name aside before anybody claims it — and point it at an email address,
  so the one account signed in with that address may claim it (which uses
  the reservation up). Hold "ben" today; assign it to the kid when he
  finally has an address. The gate holds at sign-up too — where names are
  actually claimed — and in both directions: a stranger typing the held
  name is refused in a sentence, and the person it waits for is stopped
  from spending their once-ever claim on a different name while theirs
  sits reserved. Releasing a reservation puts the name back in
  circulation; reserving can never take a name somebody already holds.
  Migration 0050 — table `reserved_name`.
- **The front page says what the app is.** A collections section — one card
  per shelf with its actual features — replaces the amiibo-heavy "everything
  else" strip, the hero names every collection, and a new section previews
  the collector's room in miniature: the same CSS furniture idea, postage-
  stamp sized.
- **The toolbar explains itself too.** A "?" at the end of every shelf's
  rail covers the dice (random pick, filter-aware, whole-shelf), the eBay
  coin, the layout toggle and the row buttons — and the help page gained
  matching sections, including the add form's quiet helpers (duplicate
  notice, retail photos, sticky defaults).
- **A "?" in every add and edit form.** Each collection's add sheet and
  entry editor now carries a small help note — what the search reaches, what
  the buttons do, and the difference between the entry and your copy. The
  help page grew matching answers: barcode scanning across all shelves,
  entry vs copy, games and hardware.
- **A typed ISBN finds the book.** The number on the back cover works in the
  title box now, hyphens and all — the same exact-edition lookup the barcode
  scanner does, for the machines that have no camera to scan with.
- **Tiles on the wanted list**, same toggle as everywhere else.
- **Book defaults in Settings** — hardcover or paperback, jacket or no jacket.
  A shelf leans one way, so those two get answered once instead of on every
  book.

### Changed
- **LEGO records the box separately.** "Complete, box & instructions" folded
  two independent facts into one word. Now a checkbox for the box and five
  states: sealed, opened, loose bricks, built, missing pieces. Sealed forces
  the box on, since it can't be true without one. Migration 0022 converts
  existing sets.

### Added
- **The Collections heading rotates.** 50 general lines plus 14 for each
  collection you actually keep — so a record collector is never asked about
  minifigs. One line per visit, not per render.

### Fixed
- **Hardware showed the games count.** A console and a cartridge share a table
  server-side, so `/api/stats` had no hardware number and the home tile
  borrowed the games one — one console read as 29 items. Both are reported
  separately now, and the games count no longer includes hardware.

### Changed
- **The mark is in the header**, and on the sign-in screen — the shelf, rather
  than the generic coin that stood in for it.
- **New collection icons**, all eight, drawn for this app rather than picked
  from a set: two overlapping cards, a controller, a disc sleeve, a record, a
  speech panel, a brick, three books on a shelf and a console.

### Fixed
- **An unreachable API asked you to sign in.** When `/api/auth/me` didn't
  answer, the app assumed accounts were on and put up an email-and-password
  form — for a server that wasn't responding, so no credentials could have
  worked. It now says the server isn't answering and points at the usual
  cause: two containers on different versions.

### Added
- **The app has a face.** Icon, favicon, maskable and Apple touch icons, and a
  web manifest — a shelf holding a book, a record, a disc and a card, drawn in
  one weight and one colour so it survives being 16px in a browser tab.
- **Installable.** Add to Home Screen now produces an app rather than a
  bookmark: standalone display, the app's own background behind the status
  bar, and an offline shell.

### Changed
- Two colour tokens moved to match the brand exactly: the panel surface, and
  the text, which was a warm cream and is now the cooler value the rest of the
  palette was designed against.

### Changed
- **Scanning a comic now names the run.** The big barcode is identical on
  every issue of a run, so it can only ever say which *run* you're holding —
  and it was filling in whatever issue the shop's listing happened to mention,
  which is the issue that shop stocked. It now looks the run up on Comic Vine
  and offers the ones by that name with the year each began, which is what
  tells five *Guardians of the Galaxy* apart. Pick one and the title and year
  fill in; the issue number is on the cover in your hand.
- The five-digit code beside the barcode still fills the issue when scanned,
  but nothing waits for it — and the hint no longer says "or just type it",
  which sent people looking for a field that doesn't exist. Type five digits
  into Issue # and the app now says what they mean and offers the issue.

### Removed
- The temporary backfill button in Settings. `python -m app.backfill` stays —
  anyone upgrading has the same gap.

### Added
- **`python -m app.backfill`** — fills in book blurbs and record tracklists on
  items added before either existed. Never overwrites, safe to re-run, and
  reports what it couldn't identify rather than guessing.

### Changed
- **Favourites are gone.** A collection was either on, or on-but-starred, and
  the two switches decided the same thing — so a collection could be turned on
  and still be nowhere. Now: on means it's on the Collections tab.
- **Three tabs: Collections, Wanted, Settings.** Collections is the page the
  wordmark already opened, showing the collections you keep rather than a
  scrolling list of all of them. Settings came down off the header, and the
  full-list sheet is gone.
- Password and email fields are styled like the rest of the app — they had
  been falling through to the browser's own boxes.

### Added
- **Lock this app** (Settings) — a password, or a short PIN for a phone, on a
  single-user install. One account, no user management, no login screen until
  you ask for one. The way Radarr and Sonarr do it.
- **Login throttling.** Five wrong answers per address and account, then a
  five-minute wait. Getting it right clears the count, so mistyping your own
  password twice costs nothing.
- `python -m app.resetpw --clear` takes the lock off from the host.

### Added
- **Optional user accounts.** `AUTH_MODE=multi` turns on a sign-in screen,
  argon2 passwords and admin-created accounts, each person getting their own
  copies, wanted list, binder and preferences. The default stays `single`:
  no login screen, nothing to configure, and an existing install upgrades
  without noticing. No reset emails — `python -m app.resetpw <email>` on the
  host is the recovery path, because requiring an SMTP server to get back into
  your own house would be worse than the problem.
- **Groundwork for user accounts** (migrations 0018–0021). Nothing signs in
  yet and nothing looks different. A `users` table exists with the current
  owner as user 1; `owned` and `wanted` record who they belong to; `dex_slots`
  and `settings` are keyed per person, so two people can't share one binder or
  overwrite each other's preferences; and `item_override` holds the photo and
  notes you attach to a shared catalogue entry.
- Every `user_id` defaults to the owner in the database, so an existing
  install upgrades with no change in behaviour.

- **A test suite and a CI gate.** Migrations reverse and re-apply without
  losing data; backup and restore round-trips; two accounts stay separate.
  19 tests on an isolated stack, and `build-push` no longer publishes an image
  unless they pass — before, every push to main tagged `latest` whether or not
  the app started.
- **A tenancy test suite** (`api/tests/test_tenancy.py`), written before the
  sweep it checks. Two real accounts through the real API: no list, count,
  binder or response body of one may contain anything of the other's.

### Fixed
- **Every collection listed everybody's items.** The rule for "what's on my
  shelf" read *owned by anyone, or wanted by nobody* — sound with one user,
  and with two it was true of everything the other one owned. A shelf is what
  you own.
- **Responses carried other people's copies.** Condition, grade, cert number
  and notes for every copy of an item, whoever owned it, were in the body of
  every list. Now only yours.
- **One binder, shared.** The Pokédex asked for cards flagged `in_binder`
  without asking whose. Found by reading the query, not by the suite — the
  suite covers it now.
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
