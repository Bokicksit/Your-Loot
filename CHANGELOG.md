# Changelog

Notable changes per tagged release. `VERSION` moves +0.01 on every commit so
that any build traces back to one, but only tagged releases are meant for
pinning — those are the ones listed here.

Full detail is in the commit log, where every change has its own note.

## [Unreleased]

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
