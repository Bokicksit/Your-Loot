# Changelog

Notable changes per tagged release. `VERSION` moves +0.01 on every commit so
that any build traces back to one, but only tagged releases are meant for
pinning — those are the ones listed here.

Full detail is in the commit log, where every change has its own note.

## [Unreleased]

### Changed
- **A failed send says why.** Every way a sync can fail arrived as one 502
  carrying whatever the far side happened to say, which for an error there
  was "Internal Server Error" — a status with no information in it. The
  message now names the cause and the next step: a refused token, a
  collection too large for a proxy in front of the receiver (with the size,
  and that Cloudflare's free plan stops at 100 MB), a timeout on a big first
  send, the receiver's own words when it refuses on plan limits, and — for a
  genuine error over there — that its logs hold the reason and nothing here
  was changed.
- **The price check does the whole binder, and says what it could not do.**
  It priced the page on screen and turning the page asked again; a binder is
  one thing and its worth is one number, so it now prices all of it, in
  slices of forty that land as they arrive — a master set of four hundred
  fills in over a few seconds with a count in the bar. Prices are green on
  the card; a card with no listing wears a red *No price data* instead of a
  quiet dash. And the bar names the sets those cards belong to — "7 not on
  TCGplayer — MEP Black Star Promos, SVP Black Star Promos" — because that is
  the actual answer: TCGdex carries no TCGplayer mapping for the promo sets,
  and seven red chips without the sentence look like seven bugs.

### Added
- **A mirror knows it is one.** A collection that arrives on a sync token
  stamps the account it lands in, and the app there draws a bar under the
  header on every page: mirror of *where*, last received *when*, changes
  here are replaced on the next send. Because the alternative was somebody
  adding a card on the hosted side and watching it vanish overnight with no
  explanation. *Receive from elsewhere* gained **Stop mirroring**, which
  clears the mark and revokes every sync token, so the old source is refused
  from then on. A person restoring their own file is not a mirror and is
  not marked.
- **Only new photographs travel.** Before it builds the zip, the sender asks
  the other side which of the files this collection points at it already
  holds, and packs the rest. Names are content hashes, so "have it" means
  the same picture. A collection with a thousand photos sends a thousand
  once and then none; an older receiver that cannot answer is sent
  everything, which is what always worked.
- **Send it a few minutes after I change something.** Every write to a
  collection marks its owner pending — the rows say so, so no route can
  forget to — and five minutes after the last change it goes. Filing twenty
  cards is one send; the public page is right before you have finished
  telling somebody about it. The nightly send is still there for people who
  would rather it happened while they slept.
- **Send your collection to another Your Loot.** The case: a collection kept
  on a home server and a public page on the hosted one, without ever putting
  the home server on the internet. *Settings → Send it elsewhere* takes the
  address of the other install and a token from the account there; the home
  server then pushes its whole collection out — now, or every night — and
  the account it lands in mirrors it. Nothing reaches in. The account over
  there is a copy and is replaced on every send, which the screen says
  plainly. Which shelves are public is still decided on the account that
  publishes them; that never travels. Almost none of it is new machinery:
  the file is the "Your collection" backup, the receiving end is the restore
  that already existed, and the token is a bearer token — with one new
  property, below.
- **A token that can do one thing.** *Settings → Receive from elsewhere*
  mints a `sync` token: it may push a collection into that account and is
  refused everywhere else — it cannot read a card, change a password, or
  make another token. The token has to live on another machine, and a
  database on somebody's NAS is not a vault; what it can do had to be small.
- **Binders keep their ids across a restore.** A restore deleted every
  binder and made new ones, so `/u/bo/binder/17` broke the moment a
  collection was loaded again — once a night, once it is mirrored. Binders
  now carry a name that survives the trip and are found again rather than
  made again; a file from before that matches set and dex binders on what
  they are of and custom ones on their name. A binder gone from the file is
  gone from the account, as it should be. That name is unique within the
  account rather than the server — it travels with the binder, so the same
  collection sent to two accounts here carries it twice, and both are right.
- **A restore checks the plan first.** It never used to, because it was
  always your own file back into your own account. A collection arriving from
  another server can be two thousand cards into a free account that allows
  three hundred, and it is refused — with the numbers — before anything is
  touched, rather than loaded and quietly over.
- **Price check, on a binder page.** Next to Arrange there is now a coin.
  Switch it on and every card on the page you are looking at gets today's
  market price laid over it, with two totals above: what the cards you own
  on that page are worth, and what the gaps would cost to fill. Switch it
  off and it is gone — nothing about a price is saved, on purpose. A price
  is a fact about this afternoon, and a table of them would be a table of
  things that used to be true. The figures are TCGplayer's market price in
  dollars, from TCGdex, which already supplies the card art; they are
  labelled with their source and age, and a dash means the card is not on
  TCGplayer. Dollars only, deliberately — TCGdex also carries Cardmarket in
  euros and it is ignored, because a page total summed across two
  currencies is not a total of anything. When the price service is down the
  bar says so rather than
  showing a page of dashes. Not eBay: eBay does not sell its sold-listings
  data to anybody this size, and TCGplayer's market price is derived from
  actual completed sales on the largest singles marketplace there is, which
  is the same question answered from a cleaner source.

### Security
- **The rate limits stop believing a header anyone can write.**
  `X-Forwarded-For` is a list a caller starts and each proxy adds to, so the
  left of it is whatever the caller typed and only the right was written by
  your own proxies. The limiter read the left, which meant a different value
  per request bought a fresh bucket per request — and the brakes on signing
  in, signing up and sending reset mail quietly did nothing to anybody who
  changed one header. It now counts in from the right by however many proxies
  are actually there (`TRUSTED_PROXIES`, 1 for every setup here), and falls
  back to the connection's own address whenever the header is too short or
  holds something that is not an address, both meaning it was not written by
  the proxies it claims. Nothing to change unless something sits in front of
  nginx — Cloudflare, a tunnel, another load balancer — in which case set it
  to 2, because guessing high is the direction that hurts. The right number
  is not something the code can work out, so an admin can open
  `/api/admin/forwarding` and be told it: Cloudflare's `CF-Connecting-IP`
  says which address really made the request, where that lands in the chain
  says how many hops are genuine, and the page either confirms the setting or
  names the number to change it to.
- **Where counting hops cannot work, `TRUST_CF_CONNECTING_IP` does.** Asked
  the above on a real deployment, it answered that no number would do: the
  forwarded chain there *begins* with a Cloudflare edge address, meaning
  something past Cloudflare discards the header and starts a fresh one, so
  the caller appears in it at no depth whatsoever. The visible cost is that
  every visitor lands on the same address — which for the signup brake means
  one bucket for the entire site, and the twenty-first stranger in an hour
  being turned away for no reason they could discover. Turning this on takes
  the address from the header Cloudflare sets, which survives whatever the
  chain does. Off by default and it must stay off unless the origin is
  unreachable except through Cloudflare: anybody who can knock directly can
  type that header themselves, which is the same hole coming in by a
  different door. `/api/admin/forwarding` now reports `shared_by_everyone`,
  which is the symptom stated plainly, and recommends this when it is the
  only thing that would help.
- **A fetched image is fetched from the address that was checked.** Pasting
  an image URL had the API resolve the hostname, satisfy itself the answer
  was not somewhere private, and then hand the *name* to the HTTP client,
  which looked it up all over again. The gap between those two lookups
  belongs to whoever owns the DNS record: answer publicly for the check,
  answer `169.254.169.254` for the fetch, and the guard is decoration. The
  connection now goes to the address that passed. The name still travels, in
  the Host header and as the TLS server name, so certificates are still
  checked against it and shared-hosting CDNs still work — there is simply no
  second question to give a different answer to.
- **Catalogue searches cost something.** Every search for a Lego set, a game,
  a film, a record, a comic, a book or a card is this server calling somebody
  else's API on this server's key, several of them metered per day. Fourteen
  such routes had no limit at all, so one signed-in client in a loop could
  spend the quota for everyone on the install. Sixty a minute per account
  now — far past what anybody reaches by typing, far under what a script
  manages — refused before the request leaves the building rather than after.
  Counted per account rather than per address, since the account is what
  spends it and moving to another network should not hand out seconds.

### Fixed
- **Collections open again on a desktop.** The room took hold of the mouse
  the instant it was pressed, so it could keep panning if the cursor ran off
  the edge. While an element holds the pointer the browser aims the click
  that follows at *it* rather than at whatever is under the cursor, so every
  click in the room arrived addressed to the floor and nothing asking "which
  collection was that?" ever got an answer. The room looked alive — it still
  scrolled, things still lit up under the cursor — and simply would not open,
  while a phone was fine throughout, because touch panning is the browser's
  own and never took the pointer in the first place. Now a press is left
  alone until it has actually travelled a few pixels, and only then becomes a
  drag. The other half of that: letting go at the end of a drag no longer
  opens whatever you happened to stop over.
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

### Fixed
- **Pictures in the Pokédex list stop giving up.** Marking a thousand
  thumbnails "low priority" was a guess, and a wrong one twice over: on this
  view the pictures are the content, and a wall of low-priority requests on
  a phone can sit behind everything else long enough to look like it never
  loaded — which is what it did, in patches, while the binder beside it drew
  the same URLs fine. The priority hint is gone, and a picture that fails is
  asked for twice more before it is given up on, so one dropped request no
  longer leaves a permanent hole.
- **A slot with no picture says so.** Owning a card the catalogue has no art
  for — about one in twenty, and worse in older sets — drew a black
  rectangle indistinguishable from something broken. It now draws a frame
  that says "no picture", still carrying the number and species, and a
  picture that fails to arrive falls back to the same frame rather than
  leaving a hole. That second half matters more since the list went lazy: a
  photograph the owner took is served with a token good for an hour, and a
  page left open longer would ask for it too late.
- **The Pokédex list stops asking for a thousand pictures at once.** Every
  slot's art was a CSS background, which the browser fetches as soon as the
  element is laid out — so opening the list put the whole dex on the wire
  and the phone served it six connections at a time, filling the wall in
  slowly and out of order. They are real images now, lazy-loaded and marked
  low priority, so the browser fetches what you are looking at and leaves
  the rest until you scroll to it. Each frame keeps its shape while empty,
  so nothing jumps as they land.
- **The Pokédex binder and list drew on top of each other.** Two mistakes
  with one cause: the drill is switched with the `hidden` attribute, which
  a declared `display` silently beats, and the file already had one block
  saying so — which the new list was appended *after*, so it never hid.
  The list is also built when its data arrives, which is later than the
  switch that should have hidden it, so it appeared visible. Both fixed,
  and the block that does the switching now says what it is and that
  nothing may follow it.
- **The card scanner finds the card instead of trusting your aim.** It was
  hit and miss, and measuring 565 real cards said why: lighting, focus,
  glare and holding the card at a tilt were all fine, and every failure was
  rotation or off-centre framing — a hand against an outline, which is the
  only way anybody holds one. Two changes answer it. The photograph now
  reaches past the outline, so a card held a few degrees off no longer
  loses its corners out of frame — margin alone took an eight-degree tilt
  from 25 of 60 to 60 of 60. And the card is then located in the shot and
  squared up before it is read, which handles what is left. Across eleven
  ways of photographing a card badly: **58% found before, 98% after**, the
  right card offered in 659 of 660, and confidently-wrong answers down from
  7 to 6. The catalogue is untouched — only the photograph is straightened,
  so nothing needs re-fingerprinting. Costs 27ms a scan.
- **A benchmark for it**, at `api/tools/bench_scanner.py`, because this was
  tuned twice on hunches and got worse the second time. Every number above
  came out of it, and it should be run before anything in `arthash.py`
  changes again.
- **Searching LEGO by name finds the set, not the video game.** Rebrickable
  catalogues the LEGO games alongside the bricks — seventeen of the
  thirty-five things called "nintendo" are Switch titles with no pieces in
  them — and answers in set-number order, so the twenty results the app
  showed were a near-random slice that left out the 2,646-piece Nintendo
  Entertainment System entirely. It now asks for the whole match list and
  ranks it: something you can build first, then how squarely the name
  answers what you typed, then size and recency. "nintendo" leads with the
  NES, "game boy" with the Game Boy. The games are still there, last —
  unfindable is its own bug.
- **Your own photos wait for focus too.** The same fix as the card scanner,
  now where it matters for pictures you keep: the guided camera — the "line
  it up against a frame" one — took whatever frame the shutter landed on.
  It asks for continuous autofocus now and keeps the sharpest of a short
  burst, saying "holding still for a sharp one" while it does. The focus
  code moved into one shared module rather than being written twice, since
  both cameras had the identical bug. The ordinary Take photo path on a
  phone is untouched and always was fine — it hands off to the phone's own
  camera app, which focuses better than we ever will.
- **The scanner waits for focus.** It used to photograph whatever was on
  screen the instant you pressed the button, so the smallest movement sent
  a smear. It now asks the camera for continuous autofocus where the device
  offers it, and — the part that actually carries it — takes a short burst
  and keeps the sharpest frame of it: seven over about a second for
  "Identify now", two for each automatic look, so the watcher stops
  spending requests on blur. Sharpness is compared only within a burst,
  never against a fixed number, because the score moves with the light.
- **The scanner stopped guessing out loud.** Reading each frame a dozen ways
  found the right card far more often, but it also let a badly framed shot
  produce a confident wrong answer — and the camera was acting on whatever
  came top, so wrong cards got picked for you. There are two bars now: the
  list a person chooses from stays generous, while the camera only decides
  by itself when the match is close enough that it cannot reasonably be
  wrong. Benchmarked on 160 real cards photographed three ways — at the new
  bar every automatic pick was correct, where the old one was wrong once in
  twenty and always on the shots you would expect. A card that will not lock
  is a card to reframe, and "Identify now" still lists the closest.
- **Three things wrong with the card scanner in the hand.** Scrolling the
  list of matches dragged the shelf behind it instead of the list — every
  modal now scrolls inside itself, the recipe the add sheets already used.
  "Scan another" came back to a black viewfinder, because hiding the
  results had unmounted the `<video>` and dropped the camera with it; the
  preview stays mounted now and the watcher picks up on the next frame.
  And the light is gone: on a glossy card it lit a reflection across the
  art, which is the one thing a fingerprint cannot see past.
- **The scanner's own test stopped flipping a coin.** It generated a
  different synthetic card every run — and only a few of those are
  matchable once deliberately mis-photographed, so the same commit passed
  locally, failed in CI, and passed on a re-run. The art is fixed now, and
  the two seeds it uses were swept for and are documented with their
  measured distances, so a failure means the matcher changed rather than
  the dice.

### Changed
- **The card scanner forgives your hands.** It wanted the card perfectly
  framed, perfectly level; now each frame is read about a dozen ways —
  straight on, nudged off-centre, cropped tighter, tilted a few degrees
  either way — and a card is scored by its best agreement with any reading.
  The catalogue side is untouched (scans are straight; the photograph is
  the crooked half), so nothing gets re-fingerprinted, and the extra work
  is a handful of 9x8 resizes that cost less than the JPEG decode before
  them. Tests now photograph the card badly on purpose.

### Added
- **The Pokédex on a public page can be read as a want list.** The binder is
  the collection as its owner arranged it; a second view shows the same
  1,025 slots as a list, with chips for **Missing** and **Needs upgrade**
  and a count on each. Every slot names its species whether or not anybody
  owns it, so a link to it tells a friend — or somebody selling — exactly
  what is still wanted, and keeps itself up to date. The Pokédex only: its
  empty slots are cards that exist in the world, where a custom binder's
  empty pocket is not a thing anybody could go and find.
- **Card art has a curation room.** A new admin section lists every English
  set with how many of its cards still lack a picture, opens into a compact
  grid of the set — name, number, art or a dashed hole — and fixes a card
  in two clicks: paste a link (copied onto this server, so it cannot rot)
  or upload a file. The picture lands on the shared catalogue row, so one
  fix reaches every collection at once. A changed picture clears that
  card's fingerprint, and a button runs the fingerprint pass in the
  background — the same one the seed script and HASH_CARD_ART run, now
  reading our own disk as happily as a CDN — counting down as it goes.
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
