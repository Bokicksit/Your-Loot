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


def fingerprint(data: bytes) -> int | None:
    """Eight bytes describing what this picture looks like, or None.

    None rather than an exception for anything unreadable: a card whose art
    404s, a truncated download, a file that claims to be a PNG. One bad image
    must not stop a run over twenty thousand of them.
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            small = im.convert("L").resize((HASH_W, HASH_H), Image.LANCZOS)
            # tobytes rather than getdata: one byte per pixel in row
            # order for an 8-bit greyscale, and not deprecated
            px = small.tobytes()
    except Exception:
        return None

    bits = 0
    for row in range(HASH_H):
        base = row * HASH_W
        for col in range(HASH_W - 1):
            bits = (bits << 1) | int(px[base + col] > px[base + col + 1])
    return bits


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
