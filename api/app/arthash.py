"""A fingerprint of a picture, small enough to keep for every card.

The catalogue knows what 20,000 cards look like, but only as URLs on somebody
else's CDN. This turns each one into eight bytes that can live in our own
database, so "which card is this a photograph of" becomes an arithmetic
question rather than a network one — and the only lookup in this app that
costs nothing to ask.

**Why a difference hash and not a checksum.** A checksum answers "are these
the same bytes", which is never true of a photograph. A dHash answers "do
these look the same", because it throws away everything a camera changes —
resolution, colour, brightness, a little blur — and keeps only which way the
brightness steps across the picture. Two photos of one card agree on that;
two different cards almost never do.

**What it cannot tell you.** It sees artwork, so it cannot separate printings
that share it: a reverse holo is the same picture as the normal print, and an
English card and its Japanese twin often are too. That is the honest limit of
the technique and it happens to sit exactly where this app already draws the
line — which printing you own is a fact about your copy, asked on the copy.
So a scan is allowed to say "this card", never "this exact one in your hand".

Nothing here is a dependency: Pillow is already how share.py makes its
preview images and how trim.py crops a photograph.
"""

import io

# Nine wide, eight tall: each row yields eight comparisons between
# side-by-side pixels, and eight rows of those is the 64 bits below. The
# extra column exists to be compared against, not to be reported.
HASH_W, HASH_H = 9, 8
BITS = 64

# How far apart two fingerprints may be and still be the same picture.
#
# Zero would demand a photograph identical to the catalogue scan, which no
# camera produces. Too generous and every card in a set looks alike, because
# they genuinely do share a frame and a colour. Twelve of sixty-four bits is
# the usual working figure for dHash on artwork, and it is applied as a
# ranking cut rather than as an answer: what comes back is a short list for
# somebody to choose from.
NEAR = 12

# How close the best match must be before the scanner is allowed to decide
# for you — as opposed to offering a list you choose from.
#
# Measured, not guessed. Against 160 real cards photographed three ways
# (clean, slightly off, badly framed), every auto-lock at ten bits or under
# was the right card: 100% of 55. Allowing twelve — the same bar the list
# uses — dropped that to 94.6%, and every single mistake came from a badly
# framed shot, which is exactly the moment the scanner should keep looking
# rather than commit. A wrong card added quietly is the worst outcome this
# feature has; waiting another second is the cheapest.
SURE = 10


def _hash_image(im) -> int:
    """The 64 bits, from an already-open greyscale-able image."""
    from PIL import Image

    small = im.convert("L").resize((HASH_W, HASH_H), Image.LANCZOS)
    # tobytes rather than getdata: one byte per pixel in row order for an
    # 8-bit greyscale, and not deprecated
    px = small.tobytes()
    bits = 0
    for row in range(HASH_H):
        base = row * HASH_W
        for col in range(HASH_W - 1):
            bits = (bits << 1) | int(px[base + col] > px[base + col + 1])
    return bits


def fingerprint(data: bytes) -> int | None:
    """Eight bytes describing what this picture looks like, or None.

    None rather than an exception for anything unreadable: a card whose art
    404s, a truncated download, a file that claims to be a PNG. One bad image
    must not stop a run over twenty thousand of them.
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            return _hash_image(im)
    except Exception:
        return None


# How the probe jitters. The catalogue side is hashed once, straight on —
# it is a scan, and scans are straight. The photograph is the crooked half:
# a hand holds the card a little off-centre, a little rotated, a little too
# far away, and a dHash forgives none of that because every comparison
# moves with the pixels. So the photo is hashed many ways and the best
# agreement wins. Small numbers on purpose: this corrects a hand, not a
# card lying sideways on a table.
_ROTATIONS = (0, -5, 5)          # degrees
_SCALES = (1.0, 0.88)            # centre crops — "a little too far away"
_SHIFT = 0.07                    # off-centre crops, as a fraction of the frame


def variants(data: bytes) -> list[int]:
    """Every plausible reading of one photograph, as fingerprints.

    Decoded once and jittered in memory: rotations of the whole frame,
    tighter centre crops, and off-centre crops for the card that missed the
    guide. About a dozen hashes, each a 9x8 resize — the whole set costs
    less than the JPEG decode did. Deduplicated, since a small jitter often
    lands on the same 64 bits.
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as raw:
            # Working copy at a modest size: the hash reads 9x8, so nothing
            # above ~256px survives anyway, and rotations get cheap.
            im = raw.convert("L")
            im.thumbnail((256, 256))
            im = im.copy()
    except Exception:
        return []

    # The straight-on reading comes from the same pipeline the catalogue
    # was hashed with, not from the thumbnail — resampling twice can move a
    # few bits, and the exact-match case should stay exact.
    out: set[int] = set()
    straight = fingerprint(data)
    if straight is not None:
        out.add(straight)
    for deg in _ROTATIONS:
        frame = im if deg == 0 else im.rotate(deg, resample=Image.BICUBIC)
        if deg != 0:
            # rotation leaves dead corners in-frame; crop past them so the
            # hash reads card, not wedge
            fw, fh = frame.size
            frame = frame.crop((int(fw * .08), int(fh * .08),
                                int(fw * .92), int(fh * .92)))
        fw, fh = frame.size
        for scale in _SCALES:
            cw, ch = int(fw * scale), int(fh * scale)
            x0, y0 = (fw - cw) // 2, (fh - ch) // 2
            out.add(_hash_image(frame.crop((x0, y0, x0 + cw, y0 + ch))))
        if deg == 0:
            # off-centre readings, straight-on only: a shifted AND rotated
            # card is two mistakes, and every variant costs every scan
            dx, dy = int(fw * _SHIFT), int(fh * _SHIFT)
            cw, ch = int(fw * .88), int(fh * .88)
            for ox, oy in ((dx, 0), (-dx, 0), (0, dy), (0, -dy)):
                x0 = max(0, min(fw - cw, (fw - cw) // 2 + ox))
                y0 = max(0, min(fh - ch, (fh - ch) // 2 + oy))
                out.add(_hash_image(frame.crop((x0, y0, x0 + cw, y0 + ch))))
    return list(out)


def to_signed(value: int | None) -> int | None:
    """The same 64 bits, as Postgres will accept them.

    BIGINT is signed and these are not, so the top half of the range is
    stored as negative. Nothing reads the number as a number — it is only
    ever compared bit for bit — so the wrap is free as long as both sides
    make it the same way.
    """
    if value is None:
        return None
    return value - (1 << BITS) if value >= (1 << (BITS - 1)) else value


def distance(a: int, b: int) -> int:
    """How many of the 64 bits disagree. Zero is the same picture."""
    return ((a ^ b) & ((1 << BITS) - 1)).bit_count()
