# The North American console-variant dataset

`consoles-na.json` is Your Loot's own catalogue of consoles, controllers and
accessories released at retail in North America — 170+ entries covering the
major machines, their famous colourways and revisions, and the controllers
and accessories a collector actually shelves. The app seeds it into the
hardware catalogue automatically on every start.

## Licence

The **facts** (names, model numbers, years, platforms) are compiled fresh
from public knowledge and released under **CC0 1.0** — use them for anything,
no attribution needed. Facts are not copyrightable; the compilation is
dedicated to the public domain anyway so nobody has to wonder.

The **images** are not part of the dataset licence. Each is a Wikimedia
Commons file — public domain or CC0, most from Evan Amos's console
photography — referenced by its stable `Special:FilePath` URL. They stay
under their own (already free) terms.

## Contributing

The dataset is deliberately conservative: NA retail releases, the famous
colourways, the iconic peripherals. Completeness comes by correction — if we
missed the Toys "R" Us gold N64, PR it.

- Edit `build_consoles_na.py`, not the JSON. The script **is** the dataset;
  the JSON is its build output. One line per entry:
  `(kind, platform, title, model_number, year, commons_file_or_None)`.
- Regenerate with `python build_consoles_na.py`.
- Verify with `python verify_images.py` — it checks every image exists on
  Commons **and** is public domain / CC0. A CC-BY photo fails on purpose:
  the app hotlinks these with no attribution UI. A variant with no free
  photo ships with `None` — an honest gap invites a photo, a broken frame
  reads as a bug.
- Commit both files together.
