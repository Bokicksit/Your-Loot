<p align="center">
  <img src="docs/logo.svg" alt="" width="96">
</p>

<h1 align="center">Your Loot</h1>

<p align="center">
  <a href="https://github.com/Bokicksit/Your-Loot/releases"><img src="https://img.shields.io/github/v/release/Bokicksit/Your-Loot?sort=semver" alt="Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-AGPL--3.0-blue" alt="Licence: AGPL v3"></a>
  <a href="https://github.com/Bokicksit/Your-Loot/actions/workflows/build-push.yaml"><img src="https://github.com/Bokicksit/Your-Loot/actions/workflows/build-push.yaml/badge.svg" alt="Build"></a>
  <img src="https://img.shields.io/badge/arch-amd64%20%7C%20arm64-informational" alt="amd64 and arm64">
</p>

Self-hosted collection tracker for **Pokémon cards, amiibo, video games,
hardware, physical movies, books, records, LEGO, and comics** — one app, one
database, one wanted list that spans all of them.

Most trackers do a single category. This one is built for people whose shelf
isn't that tidy: the Charizard you're hunting and the SNES console you're
hunting live on the same list.

<p align="center">
  <img src="docs/screenshots/wanted.jpg" alt="One wanted list holding two Pokémon cards, five PlayStation games, a LEGO set and a Blu-ray" width="32%">
  <img src="docs/screenshots/games.jpg" alt="A shelf of Dreamcast games as cover tiles" width="32%">
  <img src="docs/screenshots/scan.jpg" alt="Scanning the barcode on a SNES box" width="32%">
</p>

<p align="center">
  <em>One wanted list across everything · your shelf as its own covers · and a
  barcode fills the rest in</em>
</p>

> [!IMPORTANT]
> **Out of the box there is no login screen** — it opens straight into your
> collection, which is what you want on a home network. Two ways to change
> that: set a password or PIN in **Settings → Lock this app**, or turn on
> `AUTH_MODE=multi` for real accounts.
>
> Either way, **still don't put it on the open internet.** A lock on the app
> is not the same as hardening a server. Use a VPN or an authenticating
> reverse proxy — see [SECURITY.md](SECURITY.md) and
> [Behind a proxy or tunnel](#behind-a-proxy-or-tunnel).

<p align="center">
  <img src="docs/screenshots/collections.jpg" alt="The collections you keep, with counts" width="52%">
</p>

📖 **[User Guide](docs/USER-GUIDE.md)** — how everything works, in depth:
adding items, scanning, the binders, grading, what things are worth, backups,
troubleshooting. Inside the app, every add and edit form has a **?** that
explains its buttons in place, and **How it works** on the front page answers
the questions people actually ask.

## Contents

- [What it does](#what-it-does) — the collections, then what cuts across them
- [Quick start](#quick-start)
- [Configuration](#configuration) — every setting, in one place
- [Keeping it running](#keeping-it-running)
- [Behind a proxy or tunnel](#behind-a-proxy-or-tunnel)
- [Running on TrueNAS SCALE](#running-on-truenas-scale)
- [Running on a platform host](#running-on-a-platform-host)
- [The admin panel](#the-admin-panel)
- [Security](#security)
- [Development](#development)

## What it does

### The collections

**Cards** — search 20,000+ Pokémon cards by name, number, or set code (`151`,
`MEW`, `JTG`). Track each copy with condition, variant (holo / reverse) and
grading (PSA/BGS/CGC…, with the cert number). Cards missing from the offline
database can be pulled from TCGdex or entered by hand with your own photo. A
further 13,000 Japanese cards are available as an optional second catalogue.

**Scanning a card with the camera.** Cards have no barcode, so the camera
reads the *picture*: hold the card roughly in the outline and the app keeps
looking until it recognises it, then moves on by itself. It finds the card in
the frame and straightens it before matching, so a tilted card held a bit off
centre in ordinary room light is fine; **Identify now** takes a burst and keeps
the sharpest frame. The match is made against the artwork of every card in
your catalogue, on your own server — nothing is sent anywhere. It offers a
short list rather than one answer, because a reverse holo is the same picture
as the normal print and you're the one holding the card. Measured on 565 real
cards under eleven kinds of bad photography: 98% found, and it never picks
confidently and wrong. Needs a one-time fingerprint pass — see
[Keeping it running](#keeping-it-running).

**Pokédex binder** — a slot per national dex number, mirroring a physical
binder: one card per Pokémon, marked either *the one* or *will upgrade*.
Filter by what's missing, what wants upgrading, and by rarity.

**Binders** — as many as you keep, in two more kinds. A **set binder** is a
whole set with a slot per card, drawn from the offline catalogue: no importing,
and no filing either, because owning the card fills its slot. It shows the art
of the ones you don't own too, so a gap looks like the card it wants. A
**master set** binder has a slot per *printing* instead — normal, reverse,
Poké Ball parallel — the way the checklist in the box does. A **binder of your
own** holds whatever you choose, in the order you choose, arranged by picking a
card up and tapping where it goes, with empty pages where you want them. Tap a
blank pocket and **Put a card here** picks from your own cards, into that
pocket. A pocket holds **up to three of the exact same card** — a ×3 on the
front, each copy still its own with its own grade, pull any one out. Each
binder takes a cover and a colour, is drawn at the page size you set (3×3,
4×3, single or facing pages), and one card can be in several binders at once
— the card list shows a Pokéball for the Pokédex and a binder icon for a
binder of your own, both when it's in both.

**Price check** — on any binder, a coin next to Arrange. Switch it on and
every card in the binder gets today's **TCGplayer market price** laid over it
in green — or a red *No price data* where TCGplayer has no listing — with two
totals above: what the cards you own are worth, and what the gaps would cost
to fill. The bar names the sets with no listing, so seven red chips read as
"the promo set isn't on TCGplayer" rather than seven mysteries. It prices the copy's
actual printing — a reverse holo gets the reverse price. Switch it off and it's
gone: **nothing about a price is ever saved**, on purpose, because a price is a
fact about this afternoon. Dollars only; a dash means the card isn't listed on
TCGplayer, and it's left out of the total rather than counted as zero. The
figures come from TCGdex, need no key, and are labelled with their source and
age. When the price service is down the bar says so instead of showing a page
of dashes.

<p align="center">
  <img src="docs/screenshots/cards.jpg" alt="A card collection four across" width="46%">
  <img src="docs/screenshots/pokedex.jpg" alt="The Pokédex binder, part filled" width="46%">
</p>

**Games** — IGDB-backed search, platform/region, and per-copy completeness
(loose/CIB/sealed) and condition. Barcode scanning for boxed games. For
consoles up to the Xbox 360 era it also offers a **scan of the actual box**
from libretro-thumbnails — no key needed — instead of IGDB's key art.

**Hardware** — consoles, controllers and accessories, each knowing which of
the three it is, with model number, serial, and working status. A built-in
**North American console catalogue** — our own openly licensed dataset of 170+
consoles, famous colourways, controllers and accessories, seeded automatically
— fills the form as you type: pick "Super Nintendo" and the model number,
platform and a public-domain photo arrive with it.

**Movies** — TMDB-backed, with the physical details that matter: format
(4K/Blu-ray/DVD/VHS), edition, region code. Scanning the barcode also pulls
photographs of the actual case, so a steelbook looks like your steelbook.

**Books** — Open Library search, scan the ISBN, or **type the ISBN straight
into the title box** — same lookup, no camera. Format, edition, series, and
per-copy jacket/provenance. Graphic novels, collected editions and manga live
here rather than in Comics: they carry an ISBN.

**amiibo** — the whole line seeded as a catalogue: all 932 figures, cards,
yarns and bands from the open amiibo database, each under the id Nintendo
burned into the figure. Adding one is searching and picking it — no key — and
your copy records new in box, boxed, or loose.

**Records** — MusicBrainz search, or scan the barcode on the sleeve, which
identifies the *pressing*: label, catalogue number, country, year. Discogs, if
you add a token, knows far more pressings by barcode. Graded the way vinyl
actually is — media and sleeve independently, on the Goldmine scale. Tracklists
come along for the ride.

**LEGO** — Rebrickable-backed set search by number or name, ranked so that
"nintendo" finds the NES and Game Boy *sets* rather than the Switch games.
Theme, year, piece and minifig counts. Each copy answers two questions: whether
you kept the box, and what state the set is in — sealed, complete, loose,
built, or missing pieces.

**Comics** — Comic Vine search by series and issue. Tracks the run
(`volume_year`) and the variant cover. A raw copy carries a grade; a slabbed
one carries its CGC/CBCS number instead. Scanning a comic's barcode names the
run — the issue number is on the cover in your hand.

### Across all of them

**Barcode scanning** wherever the thing in your hand carries one — records,
books, films, games, LEGO boxes, comics. Lookups are cached, so a barcode is
only ever asked about once per install. The camera needs HTTPS.

**Sold prices** — every item, owned or wanted, has a coin in its details panel
that opens an eBay search filtered to *sold and completed* listings. The query
is built from whatever separates two listings in that collection: set and
number for a card, model number for a console, pressing for a record.

**Wanted list** — everything you're hunting, across every module, as tiles or
a list, with filters, sorting and the same sold-price shortcut. Mark something
acquired and it moves into your collection with the condition you set. Find
only the case or the manual and it records the spare while the game stays on
the hunt.

**Pictures that outlive their CDN** — most art here is a link to somebody
else's server, and links break. For every item an entitled collection owns
whose picture is a link, a copy is fetched once, slowly, in the background,
and kept beside your own photos. It's a fallback: the link is still shown
first, so corrected art upstream is still what you see; only when the link
dies does the page turn to the copy — in the app and on the public page.
Everybody self-hosted; Supporters on the hosted site. Pictures an admin adds
on the card-art page were always copies.

**Tags** — your own words on anything, across every collection: *trade*,
*graded*, *childhood*, whatever. Filter any shelf by them.

**The dice** picks one thing from a shelf at random, honouring the filters —
"what should it be tonight?".

**Tiles or a list, per collection**, with the tile size remembered per shelf.
Sort and filters are remembered too. **Tap a cover** and the row opens with
the entry's details and blurb.

**The add form does small things for you** — warns about duplicates without
stopping you, offers retail photographs of the actual package, and remembers
your defaults (the region you buy, the book format you read).

**Accounts, if you want them** — nothing by default: the app opens straight
into your collection. Set a password or a short PIN in Settings and it asks
first, the way Radarr and Sonarr do. Or run with `AUTH_MODE=multi` for proper
accounts, where everyone gets their own copies, wanted list, binders and
Pokédex off one shared catalogue — and nobody can edit or delete anybody
else's. Passwords are argon2id, sessions are signed http-only cookies, and
repeated wrong guesses are throttled. Optional open signup with email
verification and password reset, for running it as a service.

**Public profiles** — turn a collection into a page you can send somebody:
`/u/yourname`, showing only the shelves you tick, drawn as a **collector's
room** you walk through — a bookcase for the books, a wall of cases for the
games, binders for the cards. Open any shelf, open any binder. A **direct link
to one shelf** — `/u/yourname/pokedex`, `/u/yourname/binders`, `/u/yourname/games`
— opens with that layer already up, for showing one collection rather than
all of them. The Pokédex on that page can be read as a **want list**: a
binder view and a tile view, with *missing* and *needs upgrade* filters, so
the person you send it to sees what you still need. Notes, tags and serial
numbers never appear. Off by default.

**Share a collection** — any shelf, the wanted list, or a binder, as a single
HTML file with the cover art packed inside. Send it like a photo: it opens in
any browser and works with no signal. Where public profiles are on, the link
replaces the file.

**Backup & restore** — two of them. **Your collection** is yours: every item,
every copy with its condition, the wanted list, your binders and your photos,
in a file that restores into your account on any Your Loot install. **Whole
server** is the operator's copy of the machine, and it loads only into an
install with nothing in it yet. Nothing already on a server can be replaced by
a restore, by anybody. Both are plain JSON inside.

**Installable** — it's a PWA. Add it to your phone's home screen and it opens
like an app, camera and all.

## Quick start

```bash
git clone https://github.com/Bokicksit/Your-Loot.git && cd Your-Loot
cp .env.example .env      # set POSTGRES_PASSWORD
docker compose up -d
```

Open **http://localhost:8080**. It asks your name, then you're in.

The card database (~20k cards) downloads itself in the background on first
start — the app is usable immediately and cards appear within a few minutes.
Watch it if you like:

```bash
docker compose logs -f api
```

### Optional API keys

All free, all optional. Without one, that collection's online search says which
key is missing and manual entry still works. Cards, books and records need no
key at all.

| Key | For | Where |
| --- | --- | --- |
| `IGDB_CLIENT_ID` / `IGDB_CLIENT_SECRET` | game search | [Twitch dev console](https://api-docs.igdb.com/#account-creation) |
| `TMDB_API_KEY` | movie search | [themoviedb.org](https://www.themoviedb.org/settings/api) |
| `REBRICKABLE_API_KEY` | LEGO set search | [rebrickable.com](https://rebrickable.com/users/_/settings/#api) → Account → Settings → API |
| `COMICVINE_API_KEY` | comic search | [comicvine.gamespot.com/api](https://comicvine.gamespot.com/api/) |
| `DISCOGS_TOKEN` | record barcodes | [discogs.com/settings/developers](https://www.discogs.com/settings/developers) → Generate token |
| `DISCOGS_KEY` / `DISCOGS_SECRET` | the same, as a registered application | for a service rather than a person; the pair wins if both are set |

Add them to `.env` and `docker compose up -d` again.

## Configuration

Everything is an environment variable, read by the `api` container unless
marked otherwise. [`.env.example`](.env.example) carries the same list with
longer explanations; this is the reference. Defaults are what a home install
wants — **a complete install needs nothing set but the database password.**

### Accounts and access

| Setting | Default | What it does |
| --- | --- | --- |
| `AUTH_MODE` | `single` | `single` = one collection, and a login only if you set a password in Settings. `multi` = accounts, each with their own collection. |
| `OPEN_SIGNUP` | `false` | Let anybody create an account. For running it as a service; keep it off on a home server. Needs `AUTH_MODE=multi`, and claim the owner account first. |
| `PUBLIC_PROFILES` | `false` | Public pages at `/u/<name>` (or `/loot` on a single-user install), and the direct shelf links. Replaces the downloadable share in Settings when on. |
| `SECRET_KEY` | *(generated)* | Signs sessions and image links. Generated and kept on first start; set it yourself only if you run more than one `api` container — they have to agree. |
| `SESSION_HTTPS_ONLY` | `false` | Send the session cookie over HTTPS only. Set true once you're behind TLS. |
| `ALLOWED_ORIGINS` | *(empty)* | Extra browser origins allowed to call the API, comma-separated — a phone app, or a browser on another machine. Empty is right when nginx serves both. |

### Brakes

| Setting | Default | What it does |
| --- | --- | --- |
| `SIGNUP_LIMIT` | `20` | New accounts per hour from one address. |
| `LOOKUP_LIMIT` | `60` | Catalogue searches per minute, per account, across every third-party lookup — Rebrickable, IGDB, TMDB, Discogs, Comic Vine, Open Library, UPCitemdb, TCGdex (search and price check). Those keys are the server's; this stops one client spending everyone's quota. |
| `TRUSTED_PROXIES` | `1` | How many of your own proxies sit in front of the API, so the brakes know which part of `X-Forwarded-For` to believe. See [Behind a proxy or tunnel](#behind-a-proxy-or-tunnel). |
| `TRUST_CF_CONNECTING_IP` | `false` | Take the caller's address from Cloudflare's header instead of counting hops. Only where nothing can reach the API except through Cloudflare. Same section. |

Login attempts are throttled too (five wrong, then a five-minute wait, per
address and account) and so is mail (three an hour per address). Neither is
configurable; neither has ever needed to be.

### Running it as a service

Every one of these is empty on a self-hosted install, and that is the point:
the software is complete, and these exist only where somebody else pays for
the server.

| Setting | Default | What it does |
| --- | --- | --- |
| `AVAILABLE_MODULES` | *(all)* | Which collections the install carries at all, e.g. `cards,records,books,lego`. Removes the rest from the API as well as the screen. |
| `PAID_MODULES` | *(none)* | Which of those need a plan, e.g. `records,books,lego`. A collection behind this is closed, never emptied. |
| `FREE_CARD_LIMIT` / `FREE_DEX_LIMIT` / `FREE_BINDER_LIMIT` | `0` | What a free account gets: copies of cards owned, how far up the Pokédex the binder goes, binders besides the Pokédex. Zero means no limit. |
| `STRIPE_SECRET_KEY` / `STRIPE_PRICE_ID` | *(empty)* | Without both, billing does not exist — every route 404s. |
| `STRIPE_WEBHOOK_SECRET` | *(empty)* | Not optional once the other two are set; an unsigned webhook is refused. |
| `RESEND_API_KEY` / `MAIL_FROM` | *(empty)* | Verification and reset mail, and nothing else. Empty, the link is written to the log instead. |
| `PUBLIC_URL` | `http://localhost:5173` | The address people actually type; goes inside mail links and public-page metadata. |

Where the service sells something, the collector's room and the direct shelf
links are what a Supporter gets; where nothing is sold, everybody has them.

### Pictures and seeding

| Setting | Default | What it does |
| --- | --- | --- |
| `KEEP_IMAGE_COPIES` | `true` | Keep a fallback copy of every linked picture an entitled collection points at (~100 KB a card). Off, and pictures stay links only. |
| `SEED_ON_START` | `true` | Download the full card database on first start, in the background. |
| `SEED_JAPANESE` | `false` | Also seed the Japanese catalogue — 13,000 more cards — once, on the next start. |
| `CARD_ART` | *(unset)* | `tcgdex` moves card pictures off `images.pokemontcg.io` onto TCGdex's MIT-licensed asset host, once. For installs serving many people. |
| `HASH_CARD_ART` | `false` | Fingerprint new card art on every start so the camera scanner stays current. The first run is ~20,000 fetches; flip it on for an evening. |

### Containers

| Setting | Container | Default | What it does |
| --- | --- | --- | --- |
| `POSTGRES_PASSWORD` | postgres, api | — | **Required.** Compose refuses to start while it's empty. |
| `POSTGRES_USER` / `POSTGRES_DB` | postgres, api | `getloot` | Don't change on an existing install. |
| `WEB_PORT` | web | `8080` | The port the app answers on. |
| `TAG` | both | `latest` | Pin a release: `TAG=2.32`, from the [releases page](https://github.com/Bokicksit/Your-Loot/releases) **without the leading `v`**. |
| `API_UPSTREAM` | web | `api:8000` | Where nginx finds the API. Only platform hosts need it. |
| `PORT` | web | `80` | Honoured for platform hosts that assign one. |
| `DATABASE_URL` / `IMAGE_DIR` / `API_PORT` | api | *(compose sets them)* | Only when running the API outside Docker or against a managed Postgres. |

## Keeping it running

**Update:**
```bash
docker compose pull && docker compose up -d
```
Database migrations run automatically. Pin with `TAG=` to update on your own
schedule instead.

**Refresh the card database** (new sets, corrections) — weekly cron is plenty:
```bash
docker compose exec api python /seed/seed_cards.py --download
```
Only ever adds and updates catalogue entries. Your copies, wanted list, binder
picks, grades and photos are never touched.

**Japanese cards** — 13,061 cards across 124 sets, including the sets that
never had an English printing. `SEED_JAPANESE=true` and restart, or once by
hand:
```bash
docker compose exec api python /seed/seed_cards_ja.py --download
```
Once seeded, a **JP** button beside the card search brings up Japanese
printings, each showing its English species name so you can find リザードン by
typing Charizard. About 6 in 10 have artwork, which is TCGdex's coverage and
improves on its own. To undo it:
```bash
docker compose exec postgres psql -U getloot -d getloot \
  -c "delete from collection_item where source = 'tcgdex-ja';"
```

**The card scanner** needs each card's artwork fingerprinted once — eight bytes
a card, the pictures aren't kept:
```bash
docker compose exec api python /seed/hash_cards.py
```
Twenty thousand requests to TCGdex, so start it on a quiet evening; it can be
stopped and restarted, and a later run does only what's new. Or set
`HASH_CARD_ART=true` and every start fingerprints whatever was added since,
which is how a freshly seeded set becomes scannable without anybody remembering
a command. Administrators can also run it from the card-art page in the app.

**Card art for many people** — pictures are seeded pointing at
`images.pokemontcg.io`, fine for a household and less fine as somebody else's
bandwidth bill. `CARD_ART=tcgdex`, or once by hand:
```bash
docker compose exec api python /seed/backfill_art.py --dry-run
docker compose exec api python /seed/backfill_art.py
```

**amiibo** are seeded on first start too; to re-run after a new wave:
```bash
docker compose exec api python /seed/seed_amiibo.py
```

**Back up** from **Settings → Whole server** — one zip with every account's
items, copies, wanted entries and photos. Keep it somewhere that isn't this
server. At the filesystem level the `data/` directory holds the Postgres
database and your uploaded images; nothing else holds state.

**Check what's running** at `/api/health` — the API's version. The bottom of
the Settings page is the web container's. If the two disagree, one image
updated and the other didn't, which looks like the app being broken rather
than half-upgraded.

## Keeping a public page current without exposing your server

The common shape: your collection lives on a home server, and you want a
public page people can actually reach — on yourloot.app, or on any other Your
Loot — **without** putting the home server on the internet.

**Settings → Send it elsewhere** does that by pushing *out*. Your server sends
its whole collection to an account on the other install, now or every night,
and that account's public page reads from the copy. Nothing reaches in: no
tunnel to your house, no open port, no exposed page.

1. On the **receiving** account (yourloot.app, say): *Settings → Receive from
   elsewhere → Create a sync token*. Copy it — it's shown once.
2. On your **home** server: *Settings → Send it elsewhere*. Paste the address
   and the token, tick *every night* if you like, **Save**, then **Send now**.
3. On the receiving account, tick which shelves are public. That decision
   stays there; sending never changes it.

Three things to know:

- **The receiving account is a mirror.** It is replaced wholesale on every
  send. Anything you add or edit *there* is gone at the next send — keep your
  collection at home, and treat the copy as a copy.
- **The token can do one thing.** A `sync` token can push a collection into
  its account and is refused everywhere else — it cannot read a card, change
  the password, or make more tokens. It has to live on your home server, and
  that is not a vault, so what it can do had to be small. Revoke it on the
  receiving side and the next send fails.
- **The plan on the receiving account applies.** A free account on a hosted
  install has caps; a collection that would exceed them is refused, with the
  numbers, before anything changes. On a hosted service this is what a
  Supporter plan is for.

Binder links survive it: a binder keeps its id across every send, so the
`/u/name/binder/17` link you gave out keeps working.

**Send it a few minutes after I change something** does what it says: file a
card at home and the public page is right within minutes, without a send per
keystroke. Only the photos the other side doesn't have yet travel — a
collection with a thousand of them sends a thousand once, then none.

The receiving account knows it's a mirror. A bar under the header on every
page there says so, with where from and when, and *Settings → Receive from
elsewhere* has **Stop mirroring**, which clears it and revokes every sync
token so the old source is refused.

The file that travels is your **Your collection** backup, and the receiving
end is the restore that already existed — so anything the backup carries,
the mirror gets: copies with condition and grading, the wanted list, tags,
binders, your photos. What never travels: your password, plan, screen name,
which shelves are public, and the sync settings themselves.

`SYNC_ALLOW_PRIVATE=true` lets the address be a private one, for a second
Your Loot on your own network; by default a LAN address is refused, the same
way a pasted image URL is.

## Behind a proxy or tunnel

Even with a password set, **don't expose port 8080 to the internet directly.**
The lock keeps a housemate out of your collection; it is not a hardened front
door, and there's no HTTPS unless you put some in front. Either:

- **Tailscale** — reach it privately from your phone, nothing public.
- **Cloudflare Tunnel** (+ Access, if you want a login in front of the login)
  — a real HTTPS hostname. HTTPS also unlocks the cameras, since browsers only
  allow them on secure origins.

Anything in front of nginx changes one thing the app has to be told about:
**who the caller is.** The login, signup and mail brakes are counted per
address, and the address arrives in `X-Forwarded-For` — a list the caller
starts and each proxy appends to. Only the entries *your* proxies wrote mean
anything, and the app cannot count them for you.

- `TRUSTED_PROXIES=1` — the default. nginx in front, API port never
  published. Right for the compose stack as it ships.
- `TRUSTED_PROXIES=2` — a tunnel or load balancer in front of nginx **that
  appends to the header.** Cloudflare Tunnel into a NAS does this.
- `TRUST_CF_CONNECTING_IP=true` — for paths where something between
  Cloudflare and the API **throws the header away and starts over**, so the
  caller is not in it at any depth and no number works. Railway behind
  Cloudflare does this. Only safe where nothing can reach the API except
  through Cloudflare; anybody who can knock directly can write that header
  themselves.

**Don't guess.** Sign in as an admin and open `/api/admin/forwarding`. It
reads the chain off your own request and tells you which setting is right —
or says `shared_by_everyone: true`, which is the failure to look for: every
visitor landing on one address and sharing one signup bucket. Guessing high is
the dangerous direction; it starts believing entries a caller wrote.

The same tunnel provider gave two different correct answers on two installs
of this app. That's why the check exists rather than a rule of thumb.

## Running on TrueNAS SCALE

See [`deploy/compose.truenas.yaml`](deploy/compose.truenas.yaml) — paste it into
**Apps → Discover Apps → ⋮ → Install via YAML**, after editing the password and
dataset paths. It publishes port 30080, since 8080 is usually taken.

**Settings go in the YAML as literal values** under the `api` service's
`environment:` — `TRUSTED_PROXIES: "2"`, not `${TRUSTED_PROXIES:-1}`. The
`${…}` form in the repo's compose files reads a `.env` file that a TrueNAS app
doesn't have, and silently falls through to the default.

**To update it:** *Apps → Installed → Your Loot → Edit*, then **Save**. TrueNAS
pulls the images and recreates the containers — that's the whole update. Don't
run `docker compose` against a TrueNAS app from a shell; you'll fight it for
control of the stack.

## Running on a platform host

Railway, Fly, Render — anywhere that isn't compose. The web container assumes
the API answers to `api` on port 8000, which is true under compose and nowhere
else. On the **web** service:
```bash
API_UPSTREAM=<your api service host>:8000
```
`PORT` is honoured too. Point the API at a managed Postgres with
`DATABASE_URL`, set `PUBLIC_URL` to the address people type, **pin both images
to a version**, and read [Behind a proxy or tunnel](#behind-a-proxy-or-tunnel)
— a platform's edge plus Cloudflare is exactly the path where hop counting
fails and `TRUST_CF_CONNECTING_IP` is the answer. Make sure the platform's own
auto-generated domain isn't publicly serving the API, or that answer stops
being safe.

## The admin panel

The first account is the administrator. Admins are never billed, and get a
panel in Settings with:

- **Users** — every account, its plan, and a switch to comp somebody a plan by
  hand (no end date means it doesn't end).
- **Reserved names** — hold a public-profile name before anyone claims it,
  optionally for a particular email, so your kid's name is waiting when they
  sign up. Taking a name away from an account is here too.
- **Card art** — every set in the catalogue, collapsible, each card with its
  picture: replace one from a link or an upload, and it becomes the picture
  for everyone. A button runs the scanner fingerprint pass for whatever's new.
- **Repair covers** — re-fetch missing cover art across the catalogue.
- **Kept copies** — how many linked pictures have a fallback copy, how much
  disk they take, how many links failed, and a button to run a pass now.
- **Stats**, and `/api/admin/forwarding` (JSON) for the proxy check above.

## Security

What the app does on its own account, beyond argon2id passwords and signed
http-only sessions:

- **Every write checks whose it is.** Editing or deleting an entry, across all
  nine collections, requires a stake in it; another account's private row is
  404, not 403, so it doesn't confirm existence. Reads were always scoped.
- **Brakes on guessing** — login, signup, mail and third-party lookups, per
  address and per account, with `X-Forwarded-For` read from the trusted end
  only (above).
- **Pasted image URLs can't be used to reach your LAN.** The hostname is
  resolved once, refused if it points anywhere private (including cloud
  metadata addresses), and the connection goes to the address that passed —
  so a DNS record can't answer differently for the check and the fetch. Every
  redirect hop is checked the same way.
- **Uploads are streamed and capped**, and image links are signed and expire.
- **A test suite gates every image** — nothing is published to the registry
  unless the tests pass, including a cross-account tenancy sweep and the
  proxy-header cases above.

Report anything you find privately; see [SECURITY.md](SECURITY.md).

## Development

```bash
docker compose -f compose.dev.yaml up --build
```
Builds from source instead of pulling images, exposes the API on :8000
(interactive docs at `/docs`), and skips the first-run seed. Frontend-only
work: `cd web && npm install && npm run dev` — that one needs Node 20.19+ or
22+, which Vite requires. The Docker build carries its own.

**Tests** run against a throwaway stack of five API variants (single-user,
multi-user, open signup, fresh, home) and a tmpfs Postgres:
```bash
docker compose -f compose.test.yaml run --rm tests
```
It refuses to run against anything not declared disposable — two of the tests
restore backups, which is destructive by definition. CI runs the same command
before it publishes an image.

**The scanner has a benchmark**, because it was tuned on guesses twice and got
worse the second time. It downloads a few hundred real cards, photographs each
one badly on purpose in eleven ways, and prints how often the matcher finds it:
```bash
docker compose exec api python /app/tools/bench_scanner.py
```
Any change to `api/app/arthash.py` should be run through it first.

**Stack:** FastAPI + SQLAlchemy + Alembic + Postgres, React + Vite, nginx. One
`collection_item` table shared by every module, with per-module attribute
tables and separate `owned`/`wanted` records — which is why the wanted list can
span every category with a single query. Adding another module is a new
attributes table plus a router; nothing existing changes.

```
api/app/               FastAPI app, models, migrations, tenancy, rate limits
api/app/integrations/  IGDB, TMDB, TCGdex, Rebrickable, Discogs, MusicBrainz, …
api/app/arthash.py     the card scanner's fingerprint and deskew
api/app/prices.py      the binder price check
api/app/room.py, drill.py, profile_*.js/.css   the public collector's room
api/tools/             the scanner benchmark
api/tests/             the suite
web/                   React SPA + nginx
seed/                  card, amiibo and console seeders; art backfill; fingerprints
deploy/                TrueNAS compose
```

Commit messages carry the version (`VERSION` moves +0.01 per commit) and the
[CHANGELOG](CHANGELOG.md) carries the reasoning.

## Data sources & credits

- Card data: [pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data)
  and [TCGdex](https://tcgdex.dev) · Japanese cards, all card artwork and
  the TCGplayer market prices behind the price check: [TCGdex](https://tcgdex.dev) (MIT)
- Games: [IGDB](https://www.igdb.com), box scans from
  [libretro-thumbnails](https://github.com/libretro-thumbnails) ·
  Movies: [TMDB](https://www.themoviedb.org)
  (this product uses the TMDB API but is not endorsed or certified by TMDB)
- Books: [Open Library](https://openlibrary.org)
- Records: [MusicBrainz](https://musicbrainz.org), the
  [Cover Art Archive](https://coverartarchive.org) and [Discogs](https://www.discogs.com)
- amiibo: the [AmiiboAPI open database](https://github.com/N3evin/AmiiboAPI)
- Console catalogue: our own [CC0 dataset](seed/data/consoles-na.json), photos
  from [Wikimedia Commons](https://commons.wikimedia.org) (public domain /
  CC0, most by Evan Amos)
- LEGO: [Rebrickable](https://rebrickable.com) · Comics:
  [Comic Vine](https://comicvine.gamespot.com)
- Barcodes: [UPCitemdb](https://www.upcitemdb.com)
- Console logos: see [`web/public/platforms/ATTRIBUTION.md`](web/public/platforms/ATTRIBUTION.md)

Every integration is optional and free — see
[Optional API keys](#optional-api-keys).

Pokémon and all card imagery are property of Nintendo / Creatures Inc. /
GAME FREAK inc. and The Pokémon Company. This project is a personal collection
tool, unaffiliated with and unendorsed by any of them.

## License

[AGPL-3.0](LICENSE) — free to use, self-host, and modify. If you run a modified
version as a network service, you must publish your changes.
