"""How good is the card scanner, really?

    docker compose exec api python /app/tools/bench_scanner.py

Downloads a few hundred real cards once, fingerprints them as a catalogue,
then photographs each one badly on purpose and asks the matcher to find it
again. Prints a table of how often it does.

This exists because the scanner was tuned twice on guesses and got worse the
second time. Every claim in the changelog about it — "forgives your hands",
"only decides when it is sure" — came from running this, and any future
change to app/arthash.py should be run through it before it ships. A number
that moves is an argument; a hunch about blur is not.

The distortions are one-at-a-time on purpose. Averaging them hid which one
actually mattered: it turned out lighting, focus and tilt were all fine, and
the whole problem was rotation and off-centre framing — which is what led to
finding the card in the shot rather than trusting the outline.

Nothing here touches the database. It is a measurement, not a test, and it
takes a few minutes.
"""

import io
import pathlib
import random
import sys
import time

sys.path.insert(0, "/app")

CACHE = pathlib.Path("/tmp/cardbench")
# Two complete modern sets and one older one. Whole sets on purpose: cards
# from one set share a frame, a palette and a layout, which is the hardest
# thing to tell apart and the case a small sample flatters.
SETS = [("sv/sv03.5", 1, 207), ("sv/sv01", 1, 198), ("swsh/swsh12.5", 1, 160)]
SAMPLE = 60


def fetch() -> list[pathlib.Path]:
    import httpx

    CACHE.mkdir(parents=True, exist_ok=True)
    have = sorted(CACHE.glob("*.webp"))
    if len(have) > 300:
        return have
    print("fetching card art (once; cached afterwards)…", flush=True)
    with httpx.Client(timeout=25, headers={"User-Agent": "your-loot-bench/1.0"}) as c:
        for s, a, b in SETS:
            slug = s.replace("/", "_")
            for n in range(a, b + 1):
                p = CACHE / f"{slug}_{n:03d}.webp"
                if p.exists():
                    continue
                try:
                    r = c.get(f"https://assets.tcgdex.net/en/{s}/{n:03d}/low.webp")
                    if r.status_code == 200 and len(r.content) > 800:
                        p.write_bytes(r.content)
                except Exception:
                    pass
                time.sleep(0.02)
    return sorted(CACHE.glob("*.webp"))


def shoot(data, *, rot=0, dx=0, dy=0, zoom=1.0, bright=1.0, blur=0, persp=0,
          glare=0, fill=0.82, quality=70):
    """A photograph of the card, with the things a phone actually does to it.

    `fill` is how much of the frame the card takes up, and it is a setting
    rather than a constant because it turned out to matter more than
    anything else: a card filling the shot edge to edge (fill=1.0) loses its
    corners the moment it is held off straight, and a corner outside the
    picture cannot be straightened back. The default matches what the app
    captures — CAPTURE in web/src/components/CardScan.jsx photographs past
    the outline, so the card lands at about 82% of the frame. Set it to 1.0
    to see the difference that margin alone makes.
    """
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    im = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = im.size
    if persp:
        k = int(w * persp)
        im = im.transform((w, h), Image.QUAD, (k, 0, 0, h, w, h, w - k, 0),
                          resample=Image.BICUBIC)
    canvas = Image.new("RGB", (int(w * 1.3), int(h * 1.3)), (30, 30, 36))
    z = zoom * fill
    im2 = im.resize((max(8, int(w * z)), max(8, int(h * z))))
    canvas.paste(im2, (int((canvas.width - im2.width) / 2 + dx * w),
                       int((canvas.height - im2.height) / 2 + dy * h)))
    if rot:
        canvas = canvas.rotate(rot, resample=Image.BICUBIC, fillcolor=(30, 30, 36))
    if glare:
        band = Image.new("RGB", canvas.size, (0, 0, 0))
        ImageDraw.Draw(band).polygon(
            [(0, canvas.height * .30), (canvas.width, canvas.height * .05),
             (canvas.width, canvas.height * .28), (0, canvas.height * .55)],
            fill=(glare, glare, glare))
        canvas = Image.blend(canvas, band.filter(ImageFilter.GaussianBlur(40)), .35)
    gw, gh = int(canvas.width / 1.3), int(canvas.height / 1.3)
    x0, y0 = (canvas.width - gw) // 2, (canvas.height - gh) // 2
    shot = canvas.crop((x0, y0, x0 + gw, y0 + gh)).resize((300, 420))
    if blur:
        shot = shot.filter(ImageFilter.GaussianBlur(blur))
    shot = ImageEnhance.Brightness(shot).enhance(bright)
    b = io.BytesIO()
    shot.save(b, "JPEG", quality=quality)
    return b.getvalue()


CASES = [
    ("square on",       dict()),
    ("rotated 5 deg",   dict(rot=5)),
    ("rotated 8 deg",   dict(rot=8)),
    ("rotated 12 deg",  dict(rot=12)),
    ("off-centre 6%",   dict(dx=.06)),
    ("off-centre 10%",  dict(dx=.10)),
    ("tilted 6%",       dict(persp=.06)),
    ("held too far",    dict(zoom=.80)),
    ("glare",           dict(rot=2, glare=210, bright=1.05)),
    ("soft and dim",    dict(rot=4, dx=.04, blur=1.2, bright=.75)),
    ("a real bad one",  dict(rot=7, dx=.05, dy=.03, persp=.05, blur=1.0, bright=.85)),
]


def main() -> int:
    from app import arthash

    files = fetch()
    if len(files) < 100:
        print("not enough card art to measure against")
        return 1

    print(f"fingerprinting {len(files)} cards…", flush=True)
    cat = [(f.name, arthash.fingerprint(f.read_bytes())) for f in files]
    cat = [(n, h) for n, h in cat if h is not None]

    random.seed(11)
    sample = random.sample(files, min(SAMPLE, len(files)))
    print(f"\n{len(cat)} cards in the catalogue, {len(sample)} photographed per row")
    print(f"(match threshold {arthash.NEAR} bits, acts on its own under "
          f"{arthash.SURE})\n")
    print(f"  {'':18} {'found':>7} {'in top 8':>9} {'wrong+sure':>11}")

    started = time.perf_counter()
    total = shown = confident = 0
    for label, kw in CASES:
        top1 = top8 = wrong = 0
        for f in sample:
            probes = arthash.variants(shoot(f.read_bytes(), **kw))
            if not probes:
                continue
            scored = sorted(
                (min(arthash.distance(h, p) for p in probes), n) for n, h in cat
            )
            best_d, best_n = scored[0]
            if best_n == f.name:
                top1 += 1
            elif best_d <= arthash.SURE:
                wrong += 1
            if any(n == f.name for _d, n in scored[:8]):
                top8 += 1
        total += top1
        shown += top8
        confident += wrong
        print(f"  {label:18} {top1:>3}/{len(sample):<3} {top8:>5}/{len(sample):<3} "
              f"{wrong:>8}")

    n = len(CASES) * len(sample)
    print(f"\n  found {total}/{n} ({total / n * 100:.0f}%), "
          f"offered {shown}/{n}, wrong-and-confident {confident}")
    print(f"  {(time.perf_counter() - started) / n * 1000:.0f} ms per scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
