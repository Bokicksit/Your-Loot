# Your Loot — User Guide

Everything you can do with the app, and why some of it works the way it does.
If you just want it running, the [README](../README.md) has the five-minute
version.

- [First run](#first-run)
- [How Your Loot thinks](#how-your-loot-thinks)
- [Getting around](#getting-around)
- [Adding things](#adding-things)
- [Pictures](#pictures)
- [The collections](#the-collections)
  — [cards](#cards) · [Pokédex](#pokédex) · [games](#games) ·
  [hardware](#hardware) · [movies](#movies) · [books](#books) ·
  [records](#records) · [LEGO](#lego) · [comics](#comics)
- [The wanted list](#the-wanted-list)
- [Settings](#settings)
- [Backup and restore](#backup-and-restore)
- [Keeping it healthy](#keeping-it-healthy)
- [Troubleshooting](#troubleshooting)

---

## First run

Open the app and it asks two things: **what to call you**, and **what you
collect**. The name is cosmetic — it becomes "Bo's Loot" in the header. The
collections you tick decide which tabs exist.

Neither is permanent. Both live in **Settings**, and turning a collection off
later hides it without deleting anything.

If you're self-hosting, the Pokémon card database (about 20,000 cards)
downloads in the background on first start. The app is usable immediately;
cards appear over the next few minutes.

---

## How Your Loot thinks

This is the one concept worth reading. Everything else follows from it.

Your Loot separates **the thing** from **your copy of the thing**.

- A **catalog entry** is the item itself — *Chrono Trigger (1995)*, *Saga #1*,
  *OK Computer*. It holds facts that are true for everyone: the release year,
  the publisher, the set number.
- An **owned copy** is a specific object on your shelf, with *its* condition,
  *its* completeness, *its* grade. One catalog entry can have several.
- A **wanted** flag says you're hunting it.

That split is why a few things behave the way they do:

**You can own the same thing twice, differently.** A loose copy of a game and a
sealed copy are two owned records under one entry. Each has its own condition,
and you can delete one without touching the other.

On cards this is a **− 2 +** counter on the tile. **+** adds another one just
like your last — same condition and print, so pulling four of one common takes
three taps — and **−** takes the newest back off, asking first.

Copies that are identical share a chip with a count (`NM · stamped ×2`);
anything that differs gets its own. Tapping a shared chip edits **one** of
them, which then splits onto its own line — the editor says so before you
change anything. To reach a specific copy, expand the card: the panel lists
every one separately.

**You can own something *and* still want it.** Found the manual but not the
cartridge? Record the manual as a copy, and the game stays on your wanted list.
The app does this automatically — see [spare parts](#spare-parts).

**Wanted-but-unowned things don't clutter your shelves.** If you add something
as "I want it", it appears on the Wanted tab only. It shows up in the
collection once you own a copy. So the Games tab is what you *have*, not a
mixed list of have and want.

**Deleting a copy isn't deleting the entry.** The ✕ on a condition chip removes
that one copy. The trash icon deletes the whole entry and every copy under it,
and always asks first.

One exception: **cards from the offline database can't be deleted**, because
they're catalog rows shared by everyone rather than something you created.
Remove your copies instead — the card leaves your collection but stays in the
searchable catalog. Expanding such a card says so where the trash icon would
otherwise be, so the absence isn't a mystery. Cards you added by hand can be
deleted normally.

---

## Getting around

Three tabs along the bottom:

| Tab | What's there |
| --- | --- |
| **Collections** | The ones you keep — tap one to open it |
| **Wanted** | Everything you're hunting, all categories in one list |
| **Settings** | Name, collections, display, backups |

Collections is the same page the **Your Loot** wordmark opens, and it shows
exactly what you've turned on in Settings — nothing more. One switch, one
list.

If something is missing from it, a line at the bottom says how many and points
at Settings. When nothing is missing there's no line, because a permanent
notice about collections you already have is just noise.

### Opening and closing an item

Tap an item's picture or its name to expand it. Tap it again to close it.

**Opening another item closes the one before it**, so only one is ever open and
you never scroll past a column of panels you forgot about. Nothing else closes
it: the background, the toolbar, the search box, the filters and the sort menu
all leave it exactly where it is.

This works the same everywhere — all eight collections, the Pokédex slots, and
the wanted list, including its **Got it** editor.

The one exception is an **entry editor you've typed in**. Tapping off it asks
whether to discard the changes first, because losing a screen of typing to a
mis-tap on a phone is a miserable way to lose it. An editor you opened but
didn't change closes silently like anything else.

### Tiles or a list

Next to the sort dropdown are two small buttons that switch how a collection
is drawn.

**Tiles** put the picture first — a wall of covers you recognise by sight
before you've read a word. Good for browsing, for spotting the gap on a shelf,
and for anything where the artwork *is* the thing.

**List** puts the detail first — a small thumbnail on the left and the
platform, edition, year and every copy's condition legible without opening
anything. Good for checking what you actually own, and for long collections
where eight rows fit in the space three tiles would take.

The choice is saved **per collection**, so Movies can sit in tiles while Books
stays a list. Cards start as tiles and everything else starts as a list, which
is how the app looked before the buttons existed — if you never touch them,
nothing changes.

The wanted list has the same two buttons.

The Pokédex has no such switch. It's a picture of a binder, and a binder is
tiles.

### Sorting

Every collection has a **sort** dropdown next to its filters, and so does the
wanted list. The options differ per collection, because what you file a shelf
by isn't what you file a long box by:

| Collection | Sorts | Opens on |
| --- | --- | --- |
| Cards | Pokédex no. · A–Z · set · card number · rarity | Pokédex no. |
| Games | A–Z · system · year | A–Z |
| Hardware | A–Z · system | A–Z |
| Movies | A–Z · format · year | A–Z |
| Books | A–Z · author · series · year | A–Z |
| Records | artist · A–Z · label · year | artist |
| LEGO | A–Z · theme · set number · year · piece count | A–Z |
| Comics | series & issue · A–Z · publisher · cover year | series & issue |
| Wanted | A–Z · by collection | Last added |

**Last added** and **First added** are on all eight, and on the wanted list.

On **Wanted**, "last added" is the day you decided you wanted it, not the day
the catalog first heard of the item — and **by collection** groups the list
rather than filtering it, which is what the chips above it already do.

A few of these do more than they say:

- **Numbers sort as numbers**, so card #9 comes before #10 and LEGO 4002
  before 10179. Sorted as plain text — which is how they're stored, since
  plenty of them aren't numbers — 10179 would come first.
- **By series** puts a run in reading order, not alphabetical order: *Book
  One, Book Two, Book Three*, using publication year. Standalones trail.
- **Comics by series & issue** files the way a long box does — series, then
  volume, then issue. Issues with no number at all (*Annual*, *½*) sit at the
  end of their series.
- **By rarity** on cards uses the rarity ladder printed on the card, commons
  through secret rares, not the alphabet — which would file Common between
  Rainbow and Ultra.
- **By label** on records sorts by catalogue number inside each label, which
  is roughly the order that label released them.

---

## Adding things

Every collection has an **Add** button in the top-right of its page. It opens
in two steps, so the box you type a search into is never on screen next to the
boxes that describe your copy:

1. **Find it** — search the online database, or scan a barcode. Pick a result
   and you move straight to step 2 with everything it knew already filled in.
   Nothing to find? **Enter it by hand** goes to step 2 blank.
2. **Describe your copy** — format, condition, what you have, your own photo.
   The **←** in the corner goes back to the search if you picked the wrong
   thing.

Two collections skip step 1, for good reasons. **Hardware** has no online
catalogue worth searching, so it opens straight to the details. **Cards** show
each result's add panel directly under the card you picked, which already
separates finding from describing.

### 1. Scan a barcode

The quickest route for anything that came in a box: games, movies, books,
records, LEGO, comics.

Tap the scan icon. If your browser can use the camera you'll get a live
viewfinder; otherwise **type the digits under the barcode** into the box — it
runs exactly the same lookup.

**Line the barcode up inside the gold frame.** Only what's inside that window
is read, which is deliberate: it's a fraction of the picture so it's read far
more often per second, and a DVD case with two barcodes on the back can't hand
you the wrong one. Fill the width of the frame if you can — a barcode that only
spans a third of it is the usual reason a scan hangs. Your phone buzzes the
moment it catches one.

If a **lightning bolt** appears in the corner, your phone's torch can be
switched on from there — worth it for a dark shelf, and for the glossy shrink
wrap on a sealed box.

> **Camera needs HTTPS.** Browsers only allow camera access on secure origins.
> Over plain `http://` you'll see a note saying so, and the manual digit entry
> is right there. See [Remote access](../README.md#remote-access) for how to
> get HTTPS.

What a scan gets you depends on the collection:

- **Movies and games** — the product title, and photographs of the actual case.
  The title usually names the format and edition too, so a scan of a
  Blu-ray steelbook fills in "Blu-ray" and "Steelbook" for you.
- **Books** — the ISBN resolves to the exact edition in one step.
- **Records** — the barcode identifies the *pressing*, not just the album.
- **Comics — the barcode names the run, and you type the issue.** The big
  barcode is identical on *every issue of a run*, so it can't tell you which
  one you're holding — and whatever issue a shop's listing happens to mention
  is the issue that shop was selling, not yours.

  What it can do is name the comic. Scanning it looks the run up on Comic
  Vine and offers the ones by that name, each with the year it began — which
  is exactly what separates five different *Guardians of the Galaxy*. Pick
  the year off the cover and the title and year fill in. Then type the issue
  number, which is printed on the cover in your hand and quicker to read than
  any lookup.

  There's a **small five-digit code** beside the barcode (`00111` = issue 1,
  cover 1, first printing). If your scanner picks it up the issue number fills
  itself in — but it's a shortcut, not a step. Scanners read it
  inconsistently, it isn't on every book, and the number is on the cover in
  front of you.

  There's no field to type it into, because it isn't an issue number. If you
  type one in anyway the app spots it and offers what it means — `00111`
  becomes issue 1 on a tap.

  Comic Vine has no barcode endpoint at all and no API key changes that;
  `COMICVINE_API_KEY` powers the run and issue lookups.
- **LEGO** — the barcode is stored on the entry for your records, but
  Rebrickable doesn't index barcodes, so search by set number.

### 2. Search the online database

Type a title and press **Look up** (or Enter). You get a grid of matches — tap
one and the form fills in.

Each collection searches a different source, and some need a free API key. See
[what needs a key](#what-needs-a-key).

### 3. Type it in by hand

Every field is editable. Nothing requires a lookup — if the database doesn't
have your item, or you don't have a key configured, fill in what you know and
add it. The only required field is a title.

### Own it or want it

The **I own it / I want it** toggle decides where the item lands. Owned items
go to the collection with the condition you set; wanted items go straight to
the Wanted tab, and the app jumps you there so you can see it arrive.

---

## Pictures

Three ways to give something a picture, in the order the app prefers them:

**Artwork without a barcode.** Picking a film or game from the online search
also asks the retail database for photographs of the actual case, by name. The
metadata catalogues have no case art at all — TMDB holds 229 posters for Blade
Runner 2049 and every one is a theatrical poster — so this is the only route to
a picture of the thing on your shelf when you haven't scanned it. Case photos
lead the strip and one is picked for you, but never over a picture you chose
yourself. These searches share the barcode service's daily allowance.

**Artwork from the barcode.** After scanning a movie or game, a strip of
thumbnails appears labelled *case*. These are photographs of the actual box,
which is usually a better match for your shelf than a theatrical poster. The
sharpest one is picked for you; tap another to change it.

**Artwork from the database.** Picking a search result adds its poster or cover
to the same strip, labelled *poster*. If you already scanned a barcode the case
photo stays selected — the poster is there as an alternative, one tap away.

**Your own photo.** Two buttons: **Upload photo** takes one already on the
device, **Take photo** opens the camera. This is the most accurate option,
because it's *your* copy — your slipcover, your creases, your shelf. There's
also a link icon for pasting an image URL.

Either way the photo opens in a trimmer first. Drag the corners to any shape —
a card, a sleeve and a console box aren't the same proportions, so nothing is
locked to a ratio. **Snap to edges** tries to find the item for you and works
well on a plain surface; on a busy background it says so and leaves the corners
to you. **Whole photo** undoes it.

Shot at an angle? The slider straightens the photo, and the quarter-turn
buttons handle one that came in sideways. Straighten first, then hit *Snap to
edges* — it reads the picture as it stands, so a level shot is much easier for
it to find.

Notes:

- Photos are capped at **15 MB**. Oversized ones are rejected instantly,
  before uploading.
- Case photos from retailers are **copied to your own storage** when you save,
  because those links rot. Database covers stay linked to their source.
- Every collection has an **Edit entry** pencil on the row, which includes the
  picture — so a cover pulled from a database can be swapped for a photo of
  your own copy at any time.
- Removing a picture asks first. On a card from the offline database there's no
  ✕ at all while it's showing the catalog art — that picture isn't yours to
  delete. Put your own photo on and the ✕ appears, and it takes yours off.
  Should a catalog picture ever go missing, the next card-database refresh
  brings it back.

---

## What it's worth

Tap any item to open its details and there's a **coin** in the top-right
corner. It opens an eBay search filtered to *sold and completed* listings —
what people actually paid, not what sellers are asking. It's the same coin
from the wanted list, and the closest thing to a valuation without paying for
a pricing service.

Nothing is stored for this, so **everything already in your collection has one
now** — no re-adding, no refresh, no migration. Edit an item and the search
follows the edit.

The search is built from the entry, using whatever separates two listings in
that collection:

| Collection | What it searches for |
| --- | --- |
| Cards | name, card number, set — `Charizard ex 105/112 FireRed & LeafGreen` |
| Games | title and system, with our `(1996)` suffix dropped |
| Hardware | title and model number — an original and a revision aren't the same item |
| Movies | title, format, edition — a steelbook isn't a plain case |
| Books | title and author |
| Records | artist and pressing format, so you don't price the CD |
| LEGO | title and set number |
| Comics | title and variant cover |

Anything the title already says is left out rather than repeated. It's a
starting point, not an appraisal — condition, completeness and grading move
prices far more than the search can know, so read the actual sold listings.

---

## The collections

### Cards

Search 20,000+ Pokémon cards by name, card number, or set — including printed
set codes like `151`, `MEW`, `JTG`. The set box autocompletes after two
characters, and there's a button to browse the full list.

**Accents are optional.** `flabebe` finds Flabébé, `poke ball` finds Poké Ball,
`pokemon catcher` finds Pokémon Catcher. Typing the accent works too — it's
matched both ways, in every collection, so `sigur ros` finds Sigur Rós on your
records shelf.

**The number box takes exactly what's printed on the card**, letters and all.
`58`, `58/102`, `TG03`, `GG07/GG70`, `RC1/RC25` all work, and case doesn't
matter — `gg07` finds the same card as `GG07`. Leading zeros are ignored, so
`058` and `58` are the same search.

Each copy records:

- **Condition** — NM, LP, MP, HP, DMG
- **Grading** — Raw, or PSA / BGS / CGC / TAG / ACE with a numeric grade
- **Variant** — Non-Holo, Reverse Holo, Holo (your copy's print, not the
  catalog's)
- **Stamp** — promo stamps, free text
- **Pokédex** — whether this copy occupies a Pokédex slot

**Card not in the results?** Both fallbacks sit under every search, whether it
found nothing or found forty prints that aren't yours. *Search online catalog*
queries a live source for cards too new for the offline dump. *Add it manually*
takes name, dex number, set, number and rarity, and you can photograph the card
or paste an image link.

**Fixing a card you added.** Expand it and hit **Edit card** to correct the
name, dex number, set, number, total or rarity. Catalog cards don't offer this —
a database refresh would overwrite the change, so the panel says so instead.

### Pokédex

A slot per national dex number, mirroring a physical binder: **one card per
Pokémon**, not one of every card. It's the second tab at the top of the Cards
page.

Mark each slot's occupant as either:

- **The one ✓** — this is the card you want there permanently
- **Will upgrade** — a placeholder until something better turns up

Filter by **All / Missing / Needs upgrade / The one**, each showing a count,
and narrow further by rarity. Tap a Pokémon's name to jump to the card search
with it pre-filled.

Because a slot holds one card, putting a new card in a slot automatically takes
the old one out — the same swap you'd do with the physical binder. The old card
stays in your collection.

**Replace** on an occupied slot shows every other copy of that Pokémon you
already own, so you can swap without going hunting. Pick one and it takes the
slot; the card it displaced goes back to your collection, and you're asked
whether to keep it or remove that copy. If it's the only one you own, the
button offers to go find more instead.

Choose **3, 4, or 5 slots per row** in Settings.

### Games

IGDB-backed search, with the platform list narrowed to systems the game
actually shipped on once you pick a result.

**Box scans.** IGDB's cover is a game's key art — the same image whether you
own the original, the Player's Choice reprint, or a download. So once a system
is set, a scan of the *actual box front* is fetched from libretro-thumbnails
and added to the artwork strip for you to pick. It needs **no API key**, and it
follows your region: a PAL copy gets the European box where one exists.

Coverage runs from the NES to roughly the Xbox 360 — the eras that have been
archived. Newer systems, and PC, just keep the IGDB art. Changing the system
dropdown looks again, so if the first guess was wrong the right box is one
change away. Whichever image you pick is copied into your own library on save,
so it keeps working even if the source moves.

Per copy: **condition** (Mint / Good / Fair / Poor) and **what you have** —

| | |
| --- | --- |
| Sealed | Still shrink-wrapped |
| CIB | Complete in box |
| Game & case | No manual |
| Game & manual | No case |
| Loose | Cartridge or disc only |
| Case & manual (no game) | An empty box with its manual |
| Case only | |
| Manual only | |

The last three are **spare parts** — see below.

### Hardware

Consoles and accessories. Name, system, region, **model number** (SNS-001),
**serial number**, and **working status** (works / partial / broken /
untested).

Boxed hardware has a barcode like anything else — scan it and the name and
photos of the box come along. Loose retro consoles have no barcode, so those
stay typed in; the model number and serial always are, since no database knows
which unit is yours.

Accessories can be linked to a console with **Part of**, so a controller lives
under the machine it belongs to rather than floating on its own.

### Movies

TMDB-backed, with the physical details: **format** (4K UHD / Blu-ray / DVD /
VHS), **edition** (Steelbook, Criterion, Director's Cut…), **region code**, and
genre. Scanning the barcode fills format and edition from the product title and
offers photos of the actual case.

### Books

Open Library search, or scan the ISBN on the back — that resolves the exact
edition in one call. Its cover coverage is patchy, so an edition it has no
picture for borrows the jacket from the shop listing for that ISBN rather than
showing a blank tile. Format (Hardcover, Paperback, Trade Paperback, Mass
Market, Graphic Novel, Omnibus, Leather, Audiobook), year, edition, series and
ISBN. Page count comes from Open Library when a lookup finds it; there's no
field to type it in.

Per copy: condition on the book trade's scale (**Fine, Near Fine, Very Good,
Good, Fair, Poor** — collectors don't say "Mint"), plus jacket and provenance:
*With jacket, No jacket, Ex-library, Signed*.

**Graphic novels, collected editions and manga go here, not in Comics.** The
barcode decides it: a collected edition carries an **ISBN**, which Open Library
resolves, while a single issue carries a **UPC** and Comic Vine indexes no
barcodes at all. Set the format to *Graphic Novel* or *Omnibus*, then filter
Books to that format and sort **By series** — that's your graphic-novel shelf,
in reading order rather than alphabetical.

The rule of thumb: **an issue number means Comics, an ISBN means Books.** A
graphic novel has a publisher, an ISBN and a spine, and lives on a bookshelf;
what makes Comics its own collection is the things only a single issue has —
issue number, volume year, variant cover, slabbing. Author is one field, so a
writer-and-artist pair goes in as "Vaughan & Staples".

### Records

A scan tries three sources in turn. **Discogs** first if you've set a token —
it's catalogued by collectors describing the record in their hands, so it knows
far more pressings by barcode than anything else, and brings back the catalogue
number and the pressing notes ("Limited Edition, Reissue") that tell one copy
from another. Then MusicBrainz. Then, failing both, the shop listing.

MusicBrainz records barcodes unevenly, so a scan that finds nothing there falls
back to the shop listing the barcode belongs to — that fills the artist, album,
label and a photo of the sleeve, and puts any MusicBrainz releases of the same
name underneath in case one is your pressing. The scanned digits are kept
either way.

MusicBrainz search, or scan the sleeve. The barcode identifies the **pressing**
— so a 1980 Factory original and a 2011 repress stay separate entries, with
their own label, catalogue number, country and year. That's the distinction
that matters for vinyl and the one a plain album title loses.

Records are **graded twice**, because the disc and the sleeve wear
independently. You'll see two dropdowns, *Media* and *Sleeve*, both on the
Goldmine scale (Mint → Near Mint → VG+ → Very Good → Good Plus → Good → Fair →
Poor). The chip shows the pair the way collectors write it: **VG+/VG**.

Also tracked: format (12", 2x12", 10", 7", box set, CD, cassette), speed, and
free-text pressing notes for things like *180g clear vinyl*.

### LEGO

Rebrickable-backed search by **set number** or name. Set numbers carry a
variant suffix — `10276-1` — and typing just `10276` works, the app adds it.

Theme, subtheme, year, piece count, minifig count.

Per copy, how much of it survived:

| | |
| --- | --- |
| Sealed (MISB) | |
| Complete, box & instructions | |
| Complete with instructions, no box | |
| Complete, bricks only | |
| Missing pieces | |
| Parts only | **spare** |
| Instructions only | **spare** |
| Box only | **spare** |

Condition is separate: New, Like new, Used, Worn, Damaged.

### Comics

Comic Vine search by series, issue number and **volume year**. **Single issues
only** — graphic novels, collected editions and manga go in [Books](#books),
because they carry an ISBN and Comic Vine indexes issues and no barcodes at
all.

**Fill in the volume year.** It's the year the *run* started, not the cover
date — 2008 for that Guardians of the Galaxy, 1990 for the one before it. With
it, the search looks up the run first and then the one issue inside it, so you
get a handful of exact answers. Without it you get a full-text search across
every issue Comic Vine knows, which for a long-running character is hundreds of
issues cut off at the first page — the 2008 #1 you wanted may simply never
appear. The year is the same field as the one further down the form, so filling
it to narrow the search also fills it in on the entry.

If the year turns out to be wrong, the search doesn't come back empty — it
falls back to every run of that name so you can pick the right one and see what
year it actually started. Every result is labelled with its run year either
way, which is the only thing that tells six identically titled #1s apart.

Series names are matched loosely enough not to care about capitals, hyphens or
a leading "The", so *Amazing Spider-Man* finds the run Comic Vine files as
*The Amazing Spider-Man*.

Comics track the **run**, not just the series — Amazing Spider-Man #1 exists in
half a dozen volumes, so *volume year* keeps them apart — and the **variant
cover**, since a 1:25 variant is a different book to a collector.

Grading works like cards. A **raw** copy carries a letter grade (Mint, Near
Mint, Very Fine, Fine, Very Good, Good, Fair, Poor). A **slabbed** copy carries
its grader and number instead — pick CGC / CBCS / PGX / EGS and a grade from
10.0 down to 0.5, and the chip reads `CGC 9.8`. Setting the grader back to
*Raw* cracks the slab and returns you to letter grades.

---

## The wanted list

One list, every category. Filter by collection with the chips along the top.
Games and movies get a second row of chips to narrow further — by system and by
genre. Other collections don't have that sub-filter yet.

Each row expands for details. **Check sold prices on eBay** opens a
sold-and-completed search for that item — the closest thing to a market price
without a paid pricing service. The same coin sits in the corner of the details
panel on everything you already own; see [What it's
worth](#what-its-worth).

### Getting something

**Got it — move to library** opens a small editor so the copy lands with its
real condition instead of a blank record. The dropdowns match the collection:
media and sleeve grades for a record, the box ladder for a game, the survival
ladder for a LEGO set, jacket options for a book.

Confirm, and it moves into your collection and off the wanted list.

Comics get raw letter grades here. If the copy you picked up is slabbed, add it
and then set the grader on the Comics page — the acquire editor keeps to one
grade for speed.

### Spare parts

If what you found isn't the thing itself — a game's **case only**, **manual
only** or **case & manual (no game)**, or a LEGO **box only**, **instructions
only** or **parts only** — the app records the piece as an owned copy and
**leaves the item on your wanted list**. You'll see a note saying so before you
confirm.

That's the flea-market case: you found the manual, you still need the
cartridge.

### Removing something

**Remove from wanted** takes it off the list without adding it to your
collection — for when you've changed your mind. If you never owned a copy, the
entry is removed entirely rather than becoming an orphan in your library.

---

## Settings

**Collector name** — the header greeting. Blank gives you "Your Loot".

**Collections** — turn each on or off. What's on here is what's on the
Collections tab.

> Turning a collection off **hides** it. Nothing is deleted. Its items stay in
> the database and stop appearing in the menu, on Home, and in the wanted list.
> Turn it back on and everything returns exactly as it was.

**Display**

- *Pokédex slots per row* — 3, 4 or 5
- *Show Pokédex cards in the card list* — by default, cards assigned to a
  Pokédex slot are hidden from the main card list, so it shows your duplicates
  and spares. Turn this on to see everything. The same toggle sits at the top
  of the Cards tab as **Pokédex cards**.
- *Default region for new games & hardware* — NTSC-U, PAL, NTSC-J or
  Region-free. Movies use disc region codes (A/B/C, 1–4) and aren't affected.

**Backup & restore** — see below.

Settings are stored on the server, so they're the same on every device.

---

## Backup and restore

**Download backup** gives you a single `.zip` containing everything: every
item, every copy with its condition, the wanted list, the Pokédex, your
settings, and every photo you've uploaded. It's plain JSON inside, so it stays
readable and portable.

**Restore from a backup…** replaces your entire collection with the contents of
a backup file. It asks for confirmation first, and tells you afterwards how
many rows and images came back.

Things worth knowing:

- A restore is **all or nothing**. The file is fully validated before a single
  row is touched, and the replacement runs in one transaction — so a bad file
  leaves your data exactly as it was.
- Anything added *since* the backup was taken is gone after a restore. Take a
  fresh backup first if you're unsure.
- A backup from a **newer version** of Your Loot is refused rather than
  restored with pieces missing. Update first. Older backups restore fine.
- Photos are added, never deleted — restoring an old backup won't remove a
  picture you added last week.

**A backup only counts once it's off the server.** If the machine running Your
Loot is what fails, a copy sitting on it doesn't help. Move it to a different
device or cloud storage.

---

## Keeping it healthy

**Refresh the card database** — new sets and data corrections. Weekly is plenty:

```bash
docker compose exec api python /seed/seed_cards.py --download
```

This only ever adds and updates catalog entries. Your owned copies, wanted
list, Pokédex picks, grades and photos are never touched.

**Update the app:**

```bash
docker compose pull && docker compose up -d
```

Database migrations run automatically on start.

**A new collection added by an update starts switched off** if you've already
been through onboarding — so an update never resurrects a category you
deliberately turned off. Enable it in Settings when you want it.

---

## Troubleshooting

**The camera won't open for barcode scanning.**
Browsers only allow camera access over HTTPS (or on `localhost`). Type the
digits under the barcode instead — same lookup, same result. For proper camera
access from your phone, put the app behind HTTPS.

**The camera opens but never catches the barcode.**
Get the barcode filling the width of the gold frame — too small and there
aren't enough pixels per bar to read. Then check the glare: a shrink-wrapped
box under a ceiling light reflects straight back into the lens, so tilt it a
few degrees rather than holding it square on. The torch button helps in dim
rooms and hurts on gloss. Failing all that, the digits printed under the bars
go straight into the box below and run the identical lookup.

**"Barcode lookups exhausted for today."**
The free barcode service allows about 100 lookups per day per network. It
resets daily. Type the title and search instead.

**A card isn't in the database.**
The offline dump lags new releases. Use *search online* in the add form, or add
the card by hand and paste an image link.

**"X not configured — set X_API_KEY."**
That collection's online search needs a free API key. See
[what needs a key](#what-needs-a-key). Everything else about the collection
works without one, including manual entry.

**A photo won't upload.**
The limit is 15 MB, and the file must be `.jpg`, `.jpeg`, `.png` or `.webp`.
Phone photos are typically well under that.

**A restore was refused.**
If it says the backup is from a newer version, update the app and try again —
it's refusing rather than silently dropping data it can't understand.

**An item is in my collection but I still see it on the wanted list.**
That's deliberate if the copy you own is a spare part — for a game: case only,
manual only, or case & manual; for LEGO: box only, instructions only, or parts
only. Change the copy's completeness if you actually have the whole thing.

---

## What needs a key

All free, all optional. Without a key that collection's *online search* returns
a message naming the missing variable; everything else keeps working.

| Collection | Source | Key needed |
| --- | --- | --- |
| Cards | pokemon-tcg-data + TCGdex | **No** |
| Books | Open Library | **No** |
| Records | MusicBrainz | **No** |
| Records (barcodes) | Discogs | `DISCOGS_TOKEN` — optional, but much better coverage |
| Games | IGDB | `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET` |
| Movies | TMDB | `TMDB_API_KEY` |
| LEGO | Rebrickable | `REBRICKABLE_API_KEY` |
| Comics | Comic Vine | `COMICVINE_API_KEY` |
| Barcode lookup | UPCitemdb | **No** (~100/day) |

Where to get each is in [`.env.example`](../.env.example). Add them to `.env`
and restart with `docker compose up -d`.
