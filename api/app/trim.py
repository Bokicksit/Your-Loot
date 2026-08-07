"""Cut the padding off fetched artwork.

Shops and catalogues publish cover art on a canvas of their own choosing: a
portrait book cover centred in a wide white rectangle, a game box floating in
grey. The file's shape then says nothing about the picture's shape, so a
thumbnail sized from the file shows a small cover adrift in an empty box.

Trimming the uniform border fixes it once, in the stored file, for every place
the picture is ever shown. Only applied to artwork fetched from a URL — a
photo you took of your own shelf is left exactly as you took it.
"""

import io

# how far a pixel may drift from the border colour and still count as border.
# JPEG ringing puts "white" anywhere in the 240s, so an exact match finds
# nothing; too loose and it starts eating pale artwork.
TOLERANCE = 18
# a border worth rewriting the file for. Anything less is a rounding error on
# the shape and not worth re-encoding a photograph over.
MIN_TRIM = 0.03
# Only white padding is padding. Shops mat artwork onto white; nobody mats it
# onto black. Without this a game cover that happens to be dark at the edges —
# corners of (9,6,1) on a real IGDB cover — reads as "uniform border" and the
# trim eats the artwork itself.
WHITE = 240


def trim_border(data: bytes) -> bytes:
    """Return `data` with any uniform border removed, or unchanged if there
    isn't one, if the image can't be read, or if Pillow isn't installed."""
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return data
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return data  # not something we can read; store it as it came

    fmt = im.format
    if fmt == "GIF":
        return data  # could be animated, and cropping would flatten it

    rgb = im.convert("RGB")
    w, h = rgb.size
    if w < 8 or h < 8:
        return data

    # Fully transparent corners are padding too, and cropping those is always
    # safe — nothing visible is lost.
    alpha = im.convert("RGBA").getchannel("A") if im.mode in ("RGBA", "LA", "P") else None
    corners = [rgb.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    clear = alpha is not None and all(
        alpha.getpixel(p) == 0 for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))
    )
    if not clear:
        # The border colour is whatever the four corners agree on. They have to
        # agree, and they have to be white, or it isn't padding.
        if any(abs(c[i] - corners[0][i]) > TOLERANCE for c in corners for i in range(3)):
            return data
        if any(channel < WHITE for channel in corners[0]):
            return data

    if clear:
        box = alpha.point(lambda p: 255 if p > 8 else 0).getbbox()
    else:
        bg = Image.new("RGB", rgb.size, corners[0])
        mask = ImageChops.difference(rgb, bg).convert("L").point(
            lambda p: 255 if p > TOLERANCE else 0
        )
        box = mask.getbbox()
    if not box:
        return data  # the whole thing is one colour

    # only bother when there's real padding on some side
    if (box[2] - box[0]) > w * (1 - MIN_TRIM) and (box[3] - box[1]) > h * (1 - MIN_TRIM):
        return data

    cropped = im.crop(box)
    out = io.BytesIO()
    if fmt == "JPEG" and cropped.mode not in ("RGB", "L"):
        cropped = cropped.convert("RGB")  # JPEG has no alpha channel
    try:
        cropped.save(out, format=fmt or "PNG", quality=92)
    except Exception:
        return data
    return out.getvalue()
