"""A collection as one file you can send somebody.

Self-contained HTML: the pictures are inside it, so it opens on a phone with
no signal, needs no server, and keeps working long after this install is gone.
That is the point of it — a link only works while something is listening, and
most of these installs are on somebody's home network.

Three rules run through everything here.

The first is that a row is built from a named list of fields rather than by
filtering an existing one. A share is the one place in this app where getting
it wrong publishes something, and a blocklist quietly leaks the next field
somebody adds. Nothing that came out of a free-text box goes in — no notes, no
tags, no serial or certificate numbers, no summaries.

The second is that each collection's row and its sort options are declared
together, in one block, below. They were apart for a while and immediately
drifted: the share offered to sort films by a year the film row did not carry.
Adjacent is the only thing that keeps them honest.

The third is that a picture which fails to fetch is counted and reported. The
card CDN refuses a default user agent, and the first version of this swallowed
49 refusals out of 57 and produced a file that looked like the cards simply
had no art. A share quietly missing half its pictures is worse than one that
says so.
"""

import base64
import html
import io
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

from app.config import settings

# Browsers get pictures; a python default user agent gets a 403 from the
# Pokémon TCG CDN, which is where every card image lives.
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# A cover at 96px and a dex slot at 72px. The binder is 1025 rows, so its
# per-picture cost is what decides whether the file is 2MB or 3.
COVER_PX = 96
SLOT_PX = 72

IDX = "__idx"  # "sort by the order the rows were written in"

TITLES = {
    "records": "Records", "cards": "Cards", "games": "Games", "hardware": "Hardware",
    "movies": "Movies", "books": "Books", "lego": "LEGO", "comics": "Comics",
    "wanted": "Wanted list", "pokedex": "Pokédex binder",
}


class Thumbnails:
    """Fetches and shrinks, remembering what it could not get.

    Fetching runs on a small pool, and every request shares one client so the
    connection to the card CDN is opened once instead of a thousand times. In
    series, with a fresh TLS handshake each time, a full binder took over two
    minutes — long enough that nginx would give up on the request before the
    file was finished. Concurrency here is a correctness fix, not a tuning
    one.

    Results are cached by URL: a binder holds one card per Pokémon, but a
    collection can hold the same catalogue art twice.
    """

    WORKERS = 8

    def __init__(self, px: int = COVER_PX):
        self.px = px
        self.failed: list[str] = []
        self._cache: dict[str, str] = {}

    def _read(self, client: httpx.Client, url: str) -> bytes:
        # A local upload is on disk. Going out over HTTP to fetch our own file
        # would need the API to reach itself by hostname, which is not a safe
        # assumption inside a container.
        parsed = urlparse(url)
        if not parsed.scheme:
            return (Path(settings.image_dir) / Path(parsed.path).name).read_bytes()
        r = client.get(url, headers={"User-Agent": UA})
        r.raise_for_status()
        return r.content

    def _one(self, client: httpx.Client, url: str) -> str:
        try:
            im = Image.open(io.BytesIO(self._read(client, url)))
            # Straight to RGB would drop the alpha onto black. Flatten onto
            # white first — a card scanned with transparent corners belongs on
            # a page, not in a box.
            if im.mode in ("P", "LA", "RGBA") or "transparency" in im.info:
                im = im.convert("RGBA")
                ground = Image.new("RGB", im.size, (255, 255, 255))
                ground.paste(im, mask=im.split()[-1])
                im = ground
            else:
                im = im.convert("RGB")
            im.thumbnail((self.px, self.px))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=72, optimize=True)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            self.failed.append(url)
            return ""

    def prefetch(self, urls) -> None:
        """Fill the cache for a whole page at once."""
        todo = list(dict.fromkeys(u for u in urls if u and u not in self._cache))
        if not todo:
            return
        limits = httpx.Limits(max_connections=self.WORKERS)
        with httpx.Client(timeout=25, follow_redirects=True, limits=limits) as client:
            with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
                for url, uri in zip(todo, pool.map(lambda u: self._one(client, u), todo)):
                    self._cache[url] = uri

    def data_uri(self, url: str | None) -> str:
        return self._cache.get(url, "") if url else ""


def _join(*parts) -> str:
    return " · ".join(str(p) for p in parts if p not in (None, "", []))


def _copy(it) -> str:
    """What the first copy is, in the words that collection uses."""
    owned = getattr(it, "owned", None)
    if not owned:
        return ""
    o = owned[0]
    graded = " ".join(x for x in (o.grader, o.grade) if x and x != "Raw")
    return graded or _join(o.completeness, o.condition) or (o.condition or "")


def _year_in(title: str) -> str:
    """`Blade Runner 2049 (2017)` -> 2017 — the same rule the app sorts by."""
    m = re.search(r"\(([0-9]{4})\)\s*$", title or "")
    return m.group(1) if m else ""


def _pad(n) -> str:
    """Issue 7 sorts before issue 40 as text, once it is 0007."""
    return f"{n:0>4}" if n not in (None, "") else ""


# --- what a share may say ---------------------------------------------------
#
# One block per collection: the row, then the sorts that collection offers, in
# its order, naming its default. Everything a share can contain is written
# here by hand.

SPECS = {
    "records": {
        "default": "By artist",
        "row": lambda i: {
            "title": i.title,
            "meta": _join(i.attrs.artist, i.attrs.format, i.attrs.release_year),
            "badge": "/".join(
                x for x in (i.owned[0].condition, i.owned[0].sleeve_condition) if x
            ) if i.owned else "",
        },
        "sorts": [
            ("By artist", lambda i: i.attrs.artist),
            ("A–Z", lambda i: i.title),
            ("By label", lambda i: i.attrs.label),
            ("By year", lambda i: i.attrs.release_year),
            ("Last added", IDX),
            ("First added", IDX),
        ],
    },
    "cards": {
        "default": "By Pokédex no.",
        "row": lambda i: {
            "title": i.title,
            "meta": _join(
                i.attrs.set_name,
                f"#{i.attrs.card_number}" if i.attrs.card_number else None,
                i.owned[0].variant if i.owned else None,
            ),
            "badge": _copy(i),
        },
        "sorts": [
            ("By Pokédex no.", lambda i: _pad(i.attrs.national_dex_no)),
            ("A–Z", lambda i: i.title),
            ("By set", lambda i: i.attrs.set_name),
            ("By card number", lambda i: _pad(i.attrs.card_number)),
            ("By rarity", lambda i: i.attrs.rarity),
            ("Last added", IDX),
            ("First added", IDX),
        ],
    },
    "games": {
        "default": "A–Z",
        "row": lambda i: {
            "title": i.title,
            "meta": _join(i.attrs.platform_name, i.attrs.region),
            "badge": _copy(i),
        },
        "sorts": [
            ("A–Z", lambda i: i.title),
            ("By system", lambda i: i.attrs.platform_name),
            ("By year", lambda i: i.attrs.release_year),
            ("Last added", IDX),
            ("First added", IDX),
        ],
    },
    "hardware": {
        "default": "A–Z",
        "row": lambda i: {
            "title": i.title,
            "meta": _join(i.attrs.platform_name, i.attrs.region,
                          "working" if i.attrs.working else None),
            "badge": _copy(i),
        },
        "sorts": [
            ("A–Z", lambda i: i.title),
            ("By system", lambda i: i.attrs.platform_name),
            ("Last added", IDX),
            ("First added", IDX),
        ],
    },
    "movies": {
        "default": "A–Z",
        "row": lambda i: {
            "title": i.title,
            "meta": _join(i.attrs.format, i.attrs.edition, i.attrs.genre),
            "badge": _copy(i),
        },
        "sorts": [
            ("A–Z", lambda i: i.title),
            ("By format", lambda i: i.attrs.format),
            # films carry their year in the title and nowhere else
            ("By year", lambda i: _year_in(i.title)),
            ("Last added", IDX),
            ("First added", IDX),
        ],
    },
    "books": {
        "default": "A–Z",
        "row": lambda i: {
            "title": i.title,
            "meta": _join(i.attrs.author, i.attrs.format, i.attrs.publish_year),
            "badge": _copy(i),
        },
        "sorts": [
            ("A–Z", lambda i: i.title),
            ("By author", lambda i: i.attrs.author),
            ("By series", lambda i: i.attrs.series),
            ("By year", lambda i: i.attrs.publish_year),
            ("Last added", IDX),
            ("First added", IDX),
        ],
    },
    "lego": {
        "default": "A–Z",
        "row": lambda i: {
            "title": i.title,
            "meta": _join(i.attrs.set_number, i.attrs.theme, i.attrs.release_year,
                          f"{i.attrs.piece_count} pieces" if i.attrs.piece_count else None),
            "badge": _copy(i),
        },
        "sorts": [
            ("A–Z", lambda i: i.title),
            ("By theme", lambda i: i.attrs.theme),
            ("By set number", lambda i: _pad(i.attrs.set_number)),
            ("By year", lambda i: i.attrs.release_year),
            ("By piece count", lambda i: _pad(i.attrs.piece_count)),
            ("Last added", IDX),
            ("First added", IDX),
        ],
    },
    "comics": {
        "default": "By series & issue",
        "row": lambda i: {
            "title": i.title,
            "meta": _join(i.attrs.series,
                          f"#{i.attrs.issue_number}" if i.attrs.issue_number else None,
                          i.attrs.publisher),
            "badge": _copy(i),
        },
        "sorts": [
            ("By series & issue",
             lambda i: f"{i.attrs.series or ''} {_pad(i.attrs.issue_number)}"),
            ("A–Z", lambda i: i.title),
            ("By publisher", lambda i: i.attrs.publisher),
            ("By cover year", lambda i: i.attrs.cover_year),
            ("Last added", IDX),
            ("First added", IDX),
        ],
    },
    "wanted": {
        "default": "Last added",
        "row": lambda w: {
            "title": w.title,
            "meta": _join(TITLES.get(w.module, w.module), w.detail),
            "badge": w.badge or "",
        },
        "sorts": [
            ("Last added", IDX),
            ("First added", IDX),
            ("A–Z", lambda w: w.title),
            ("By collection", lambda w: w.module),
        ],
    },
}

CSS = """
:root{--bg:#0b0a0e;--panel:#131119;--line:#26232f;--text:#efeaf6;--mute:#6e6980;--gold:#f2b73c;--jade:#58d9a8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:26px 16px 64px}
h1{margin:0 0 3px;font-size:21px;letter-spacing:-.01em}
.sub{margin:0 0 16px;font:11px/1.5 ui-monospace,Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--mute)}
.bar{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:0 0 16px}
.bar button,.bar select{font:inherit;font-size:12px;padding:7px 12px;border-radius:999px;color:#a8a2b3;background:#1b1a22;border:1px solid var(--line)}
.bar button{cursor:pointer}
.bar button.on{color:#2a1c04;background:linear-gradient(180deg,#ffd784,var(--gold));border-color:#b57d18;font-weight:700}
ul{list-style:none;margin:0;padding:0;display:grid;gap:5px}
li{display:flex;align-items:center;gap:11px;padding:8px 11px;background:var(--panel);border:1px solid var(--line);border-radius:9px}
li[data-s="missing"]{border-style:dashed;opacity:.7}
.no{flex:none;width:42px;font:11px/1 ui-monospace,Menlo,monospace;color:var(--mute);letter-spacing:.04em}
img,.ph{flex:none;width:36px;height:50px;object-fit:cover;border-radius:4px;background:#000}
.ph{border:1px dashed var(--line);background:transparent}
.t{flex:1;min-width:0}
.t strong{display:block;font-size:14px;font-weight:550;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.t small{display:block;font:10.5px/1.5 ui-monospace,Menlo,monospace;letter-spacing:.04em;text-transform:uppercase;color:var(--mute);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pill{flex:none;font:10px/1 ui-monospace,Menlo,monospace;padding:5px 8px;border-radius:999px;white-space:nowrap;color:var(--gold);background:rgba(242,183,60,.12);border:1px solid rgba(242,183,60,.45)}
.pill.one{color:var(--jade);background:rgba(88,217,168,.12);border-color:rgba(88,217,168,.45)}
.pill.gap{color:var(--mute);background:transparent;border-color:var(--line)}
footer{margin-top:24px;font:10.5px/1.6 ui-monospace,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);text-align:center}
"""

# An empty field sorts last rather than first: a run of blank rows at the top
# looks like the sort failed.
SORT_JS = """<script>
var L=document.querySelector('ul'),O=[].slice.call(L.children),S=document.getElementById('s');
function sortList(v){
 var k=v.replace('-',''),rev=v.charAt(0)=='-',a=O.slice();
 if(k)a.sort(function(x,y){var p=x.dataset[k]||'',q=y.dataset[k]||'';
  if(!p!=!q)return p?-1:1;
  return p.localeCompare(q,undefined,{numeric:true,sensitivity:'base'})});
 if(rev)a.reverse();
 a.forEach(function(li){L.appendChild(li)})}
S.value=S.dataset.def;sortList(S.value);
</script>"""

# Coming back to All restores the summary line rather than replacing it with a
# count of everything, which is the one number the page already shows.
FILTER_JS = """<script>
var L=document.querySelector('ul'),B=document.querySelectorAll('.bar button'),
    C=document.getElementById('c'),D=C.textContent;
function show(f){var n=0;
 [].forEach.call(L.children,function(li){var ok=f=='all'||li.dataset.s==f;li.style.display=ok?'':'none';if(ok)n++});
 [].forEach.call(B,function(b){b.classList.toggle('on',b.dataset.f==f)});
 C.textContent=f=='all'?D:n+' of '+L.children.length+' slots'}
</script>"""


def _page(title, subtitle, controls, rows, script, sub_id=""):
    ident = f' id="{sub_id}"' if sub_id else ""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f'<div class="wrap"><h1>{html.escape(title)}</h1>'
        f'<p class="sub"{ident}>{html.escape(subtitle)}</p>'
        f"{controls}<ul>{rows}</ul>"
        "<footer>Shared from Your Loot</footer></div>\n"
        f"{script}\n</body>\n</html>\n"
    )


def build_collection(scope, items, owner, with_images=True):
    """One collection, as a list. Returns (html, failed picture count).

    Rows are written in the order they arrived — newest first — so the two
    added sorts need no stored date, only the position. Every other sort reads
    a key attached to its row.
    """
    spec = SPECS[scope]
    th = Thumbnails(COVER_PX)
    keyed = [s for s in spec["sorts"] if s[1] is not IDX]
    if with_images:
        th.prefetch(getattr(i, "image_url", None) for i in items)

    out = []
    for n, it in enumerate(items):
        r = spec["row"](it)
        uri = th.data_uri(getattr(it, "image_url", None)) if with_images else ""
        pic = f'<img src="{uri}" alt="" loading="lazy">' if uri else '<span class="ph"></span>'
        keys = "".join(
            f' data-k{j}="{html.escape(str(fn(it) or ""))}"'
            for j, (_, fn) in enumerate(keyed)
        )
        badge = f'<span class="pill">{html.escape(r["badge"])}</span>' if r["badge"] else ""
        out.append(
            f'<li{keys}><span class="no">{n + 1}</span>{pic}'
            f"<span class=\"t\"><strong>{html.escape(r['title'] or '')}</strong>"
            f"<small>{html.escape(r['meta'])}</small></span>{badge}</li>"
        )

    # the two added sorts are the shipped order, forwards and backwards
    values, default = [], ""
    for label, fn in spec["sorts"]:
        v = ("" if label.startswith("Last") else "-") if fn is IDX \
            else f"k{keyed.index((label, fn))}"
        values.append((v, label))
        if label == spec["default"]:
            default = v

    opts = "".join(f'<option value="{v}">{html.escape(lab)}</option>' for v, lab in values)
    controls = (
        f'<div class="bar"><select id="s" data-def="{default}" '
        f'onchange="sortList(this.value)">{opts}</select></div>'
    )
    title = f"{owner}'s {TITLES[scope]}" if owner else TITLES[scope]
    page = _page(title, f"{len(out)} items · {date.today():%d %b %Y}",
                 controls, "".join(out), SORT_JS)
    return page, len(th.failed)


def build_pokedex(entries, owner, with_images=True):
    """The binder. No sort — a binder is an ordered thing and the dex number
    is that order; re-sorting it alphabetically would destroy the only
    structure it has. The controls filter instead, which is the question this
    page gets asked: show me the ones still missing.

    The empty slots are in on purpose. Somebody reading a binder share is
    looking for the gaps.
    """
    th = Thumbnails(SLOT_PX)
    if with_images:
        th.prefetch(e["card"]["image_url"] for e in entries if e.get("card"))

    out = []
    counts = {"missing": 0, "upgrade": 0, "one": 0}
    for e in entries:
        card = e.get("card")
        if not card:
            state, pill, meta = "missing", '<span class="pill gap">missing</span>', ""
        else:
            state = "one" if e.get("final") else "upgrade"
            pill = ('<span class="pill one">the one</span>' if state == "one"
                    else '<span class="pill">upgrade</span>')
            meta = _join(card.get("set_name"),
                         f"#{card['card_number']}" if card.get("card_number") else None)
        counts[state] += 1
        uri = th.data_uri(card.get("image_url")) if (with_images and card) else ""
        pic = f'<img src="{uri}" alt="" loading="lazy">' if uri else '<span class="ph"></span>'
        out.append(
            f'<li data-s="{state}"><span class="no">#{e["dex_no"]:03d}</span>{pic}'
            f'<span class="t"><strong>{html.escape(e["name"] or "")}</strong>'
            f"<small>{html.escape(meta)}</small></span>{pill}</li>"
        )

    total = len(out)
    buttons = [("all", f"All ({total})"), ("missing", f"Missing ({counts['missing']})"),
               ("upgrade", f"Needs upgrade ({counts['upgrade']})"),
               ("one", f"The one ({counts['one']})")]
    controls = '<div class="bar">' + "".join(
        f'<button class="{"on" if f == "all" else ""}" data-f="{f}" '
        f"onclick=\"show('{f}')\">{html.escape(lab)}</button>"
        for f, lab in buttons
    ) + "</div>"

    title = f"{owner}'s Pokédex binder" if owner else "Pokédex binder"
    filled = counts["one"] + counts["upgrade"]
    page = _page(title, f"{filled} of {total} slots filled · {date.today():%d %b %Y}",
                 controls, "".join(out), FILTER_JS, sub_id="c")
    return page, len(th.failed)
