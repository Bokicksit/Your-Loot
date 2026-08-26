/* Drilling into a piece of furniture.

   The room is the poster; this is the collection. Everything it needs is
   already on the page except one thing — a binder's pockets, which are
   fetched when a binder is opened, because a Pokedex is a thousand of them.

   No framework. This page is served to strangers with no session and has to
   be a document first, so the drill is an addition to it rather than the
   thing that draws it: with scripting off, the room and the carousels are
   still there, and only the binder spread is missing.
*/
(function () {
  var room = document.querySelector(".room2");
  if (!room) return;
  /* The one address this page answers on — /u/<name>, or /loot on a home
     server. Data is fetched under it so the page and its data travel
     together through whatever is in front of the server. */
  var base = room.getAttribute("data-base") || "";
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ------------------------------------------------------ the layer */

  function drillFor(el) {
    var z = el.closest(".zone");
    return z ? document.getElementById("drill-" + z.getAttribute("data-scope")) : null;
  }

  var narrow = window.matchMedia("(max-width: 700px)");

  /* ------------------------------------------------- the address bar

     Every shelf has an address of its own, so the one in the bar has to be
     the shelf actually on screen: arrive at /u/bo/pokedex, back out to the
     room, and a URL still saying "pokedex" is a link that copies wrong.

     replaceState rather than pushState on purpose. Opening a piece of
     furniture is looking around one page, not travelling to another, and a
     back button that walked out through every shelf somebody glanced at —
     before finally leaving the site — would be the more annoying bug. Back
     still means "wherever I came from".

     `settling` covers the one moment this must not fire: applying the focus
     a link arrived with. /u/bo/binders and /u/bo/cards open the same layer,
     and rewriting one into the other under somebody who just followed a
     link would be answering a different question than the one they asked.
  */
  var settling = true;

  function scopeOf(d) {
    return d && d.id ? d.id.replace(/^drill-/, "") : "";
  }

  function address(suffix) {
    if (settling || !window.history || !history.replaceState) return;
    var next = base + (suffix ? "/" + suffix : "");
    if (next === location.pathname) return;
    try {
      history.replaceState(null, "", next + location.search);
    } catch (err) {
      /* A file:// or sandboxed viewing of this page cannot rewrite its own
         address. The room still works; only the bar goes stale. */
    }
  }

  function openDrill(d) {
    if (!d) return;
    document.querySelectorAll(".drill").forEach(function (x) {
      x.hidden = x !== d;
      if (x !== d) x.classList.remove("on", "full");
    });
    room.classList.add("drilled");
    d.classList.add("on");
    place(d);
    address(scopeOf(d));
    var h = d.querySelector(".drill-head h3");
    if (h) h.setAttribute("tabindex", "-1"), h.focus({ preventScroll: true });
  }

  /* Out of the room and onto the screen, or back into it.

     It has to leave the element as well as cover it: the room is a size
     container, and containment makes it the containing block even for
     something fixed, so a layer left inside it stays inside it however it
     is positioned. Which side of that line the page is on can change while
     the layer is open — a phone turned on its side is a different screen —
     so this is one function, called again on resize. */
  function place(d) {
    if (narrow.matches) {
      if (d.parentElement !== document.body) document.body.appendChild(d);
      d.classList.add("full");
      document.documentElement.style.overflow = "hidden";
    } else {
      if (d.parentElement === document.body) room.appendChild(d);
      d.classList.remove("full");
      document.documentElement.style.overflow = "";
    }
  }

  function close() {
    document.documentElement.style.overflow = "";
    room.classList.remove("drilled");
    address("");
    document.querySelectorAll(".drill").forEach(function (x) {
      x.hidden = true;
      x.classList.remove("on", "full");
      if (x.parentElement === document.body) room.appendChild(x);
    });
    shut();
  }

  /* On the document rather than on the room: once the layer is open on a
     phone it is no longer inside the room, so a listener there would never
     hear the button that closes it. */
  document.addEventListener("click", function (e) {
    var zone = e.target.closest(".zone");
    if (zone && !e.target.closest(".drill")) openDrill(drillFor(zone));
    if (e.target.closest(".drill-head .close")) close();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (document.querySelector(".detail")) shut();
    else if (room.classList.contains("drilled")) close();
  });

  /* A zone is a button in everything but name, so it answers to a keyboard. */
  document.querySelectorAll(".zone").forEach(function (z) {
    z.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDrill(drillFor(z)); }
    });
  });

  /* ------------------------------------------------- the detail card */

  function shut() {
    var d = document.querySelector(".detail");
    if (d) d.remove();
  }

  function detail(el) {
    shut();
    var art = el.getAttribute("data-art") || "";
    var box = document.createElement("div");
    box.className = "detail";
    var card = document.createElement("div");
    card.className = "detail-card";
    var big = document.createElement("div");
    big.className = "big " + (el.getAttribute("data-shape") || "tall");
    /* Same as the tile: the colour is what stands in for a picture, not a
       band around one. */
    if (!art) big.style.color = el.getAttribute("data-colour") || "";
    else big.style.backgroundColor = "var(--bg-2)";
    if (art) {
      big.style.backgroundImage = "url('" + art.replace(/'/g, "%27") + "')";
      /* The tile already decided whether this picture is a shape that fills
         its frame or one that has to be fitted inside it. Deciding again
         here is how the two end up disagreeing. */
      big.style.backgroundSize = el.getAttribute("data-fill") || "cover";
      big.style.backgroundRepeat = "no-repeat";
      big.style.backgroundPosition = "center";
    }
    var info = document.createElement("div");
    info.className = "info";
    var h = document.createElement("h4");
    h.textContent = el.getAttribute("data-title") || "";
    info.appendChild(h);
    var meta = el.getAttribute("data-meta");
    if (meta) {
      var s = document.createElement("div");
      s.className = "sub";
      s.textContent = meta;
      info.appendChild(s);
    }
    var badge = el.getAttribute("data-badge");
    if (badge) {
      var chips = document.createElement("div");
      chips.className = "chips";
      var c = document.createElement("span");
      c.className = "cond";
      c.textContent = badge;
      chips.appendChild(c);
      info.appendChild(chips);
    }
    var x = document.createElement("button");
    x.type = "button";
    x.className = "close";
    x.setAttribute("aria-label", "Close");
    x.innerHTML = '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
      + ' stroke-width="1.8" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';
    card.appendChild(big);
    card.appendChild(info);
    card.appendChild(x);
    box.appendChild(card);
    box.addEventListener("click", function (e) {
      if (e.target === box || e.target.closest(".close")) shut();
    });
    (document.querySelector(".drill:not([hidden])") || room).appendChild(box);
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest(".tile-item, .loose-card, .pocket:not(.empty), .slotcell");
    if (t) detail(t);
  });

  /* A row of tiles is wider than the screen on purpose; this is the nudge
     for anybody without a trackpad. It wraps rather than stopping, because
     stopping at the end looks like something broken. */
  document.addEventListener("click", function (e) {
    var b = e.target.closest(".carousel .more");
    if (!b) return;
    var track = b.closest(".carousel").querySelector(".track");
    var step = Math.max(160, track.clientWidth - 60);
    var at = track.scrollLeft + step;
    track.scrollTo({
      left: at >= track.scrollWidth - track.clientWidth - 4 ? 0 : at,
      behavior: still ? "auto" : "smooth",
    });
  });

  /* ------------------------------------------------ the open binder */

  var GAP = 6, PADX = 24, PADY = 28, POCKET = 6, CAP = 26, CAP_TIGHT = 13;
  var cache = {};

  function fetchBinder(id, then) {
    if (cache[id]) return then(cache[id]);
    var r = new XMLHttpRequest();
    r.open("GET", base + "/binder/" + id, true);
    r.onload = function () {
      if (r.status !== 200) return;
      cache[id] = JSON.parse(r.responseText);
      then(cache[id]);
    };
    r.send();
  }

  /* One measured number decides the whole spread.

     A binder is not a grid that happens to hold cards — it is a fixed number
     of pockets of a fixed shape, and whichever of the two directions runs
     out first is the one that sets the size. So both are worked out and the
     smaller wins, which is why a 4x4 binder and a 3x3 one look right in the
     same box without either being told about the other. */
  function fit(body, b, boards, cap) {
    var availW = body.clientWidth - 32;
    var availH = body.clientHeight - 32 - 54;
    var perW = (availW - 16) / boards;

    var rowH = (availH - PADY - GAP * (b.rows - 1)) / b.rows;
    var byH = (rowH - cap - POCKET) * 5 / 7;
    var byW = (perW - PADX - GAP * (b.cols - 1)) / b.cols - POCKET;

    var artW = Math.max(16, Math.min(byH, byW));
    return {
      art: artW,
      w: Math.round(artW * b.cols + POCKET * b.cols + GAP * (b.cols - 1) + PADX),
      h: Math.round((artW * 7 / 5 + cap + POCKET) * b.rows + GAP * (b.rows - 1) + PADY),
    };
  }

  function measure(body, b, boards) {
    var size = fit(body, b, boards, CAP);
    /* Below about this, the name under a card is three letters and an
       ellipsis, which tells nobody anything and costs the card the room to
       be seen. The number stays — that is what a pocket is called.

       Measured against a real one rather than guessed: "Charmander" at this
       size is fifty pixels of text, so a pocket narrower than that has
       nothing to gain by keeping the line. */
    var tight = size.art < 52;
    if (tight) size = fit(body, b, boards, CAP_TIGHT);
    size.tight = tight;
    return size;
  }

  function pocket(slot, j, tight) {
    var el = document.createElement(slot ? "button" : "div");
    if (slot) el.type = "button";
    var owned = slot && slot[3];
    el.className = "pocket" + (owned ? " owned" : " empty");
    el.style.setProperty("--j", j);
    var art = document.createElement("div");
    art.className = "art";
    if (owned && slot[2]) {
      art.style.backgroundImage = "url('" + slot[2].replace(/'/g, "%27") + "')";
      art.style.backgroundSize = "cover";
      art.style.backgroundPosition = "center";
    }
    el.appendChild(art);
    var no = document.createElement("span");
    no.className = "no";
    no.textContent = slot ? slot[0] : "";
    el.appendChild(no);
    if (!tight) {
      var nm = document.createElement("span");
      nm.className = "nm";
      nm.textContent = slot ? slot[1] : "";
      el.appendChild(nm);
    }
    if (slot && owned) {
      el.setAttribute("data-title", slot[1] || slot[0]);
      el.setAttribute("data-meta", slot[4] || slot[0] || "");
      el.setAttribute("data-art", slot[2] || "");
      el.setAttribute("data-shape", "tall");
      el.setAttribute("data-colour", "#2a2533");
    }
    return el;
  }

  function board(b, page, side, size) {
    var per = b.cols * b.rows;
    var el = document.createElement("div");
    el.className = "board " + side;
    el.style.width = size.w + "px";
    el.style.height = size.h + "px";
    /* The stylesheet holds a board to 46% so that two of them and the rings
       fit side by side. The number here already accounts for how many boards
       there are, and a binder read one page at a time is entitled to the
       whole width — so the guard is dropped rather than fought with. */
    el.style.maxWidth = "none";
    /* Page -1 is the inside of the front cover: a binder opens onto card,
       not onto page one, and drawing it as a page would put a phantom page
       in front of the first real one. */
    if (page < 0 || page >= b.pages) {
      var blank = document.createElement("div");
      blank.className = "page-blank";
      blank.innerHTML = "<span>" + (page < 0 ? "" : "end") + "</span>";
      el.appendChild(blank);
      return el;
    }
    var grid = document.createElement("div");
    grid.className = "page-grid" + (size.tight ? " tight" : "");
    grid.style.gridTemplateColumns = "repeat(" + b.cols + ", minmax(0, 1fr))";
    grid.style.gridTemplateRows = "repeat(" + b.rows + ", minmax(0, 1fr))";
    for (var k = 0; k < per; k++) {
      grid.appendChild(pocket(b.slots[page * per + k], k, size.tight));
    }
    el.appendChild(grid);
    var n = document.createElement("span");
    n.className = "page-num";
    n.textContent = page + 1;
    el.appendChild(n);
    return el;
  }

  function icon(d) {
    return '<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
      + ' stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
      + '<path d="' + d + '"/></svg>';
  }

  /* The page that is going over.

     Laid on the page that has just arrived, at exactly its size and in
     exactly its place: hinged at the rings where there are two pages, and at
     the page's own edge where there is one. It takes itself away when the
     animation ends rather than on a timer — a timer is a second opinion
     about how long the animation lasts, and the two disagree the moment
     anybody changes it. */
  function leafOver(wrap, size, dir, twin) {
    var page = (dir < 0 && twin ? wrap.querySelector(".board.left") : null)
      || wrap.querySelector(".board.right") || wrap.querySelector(".board");
    if (!page) return;
    var leaf = document.createElement("div");
    leaf.className = "leaf" + (dir < 0 ? " prev" : "");
    leaf.style.setProperty("--leaf-w", size.w + "px");
    /* Laid out against where the page *is*, not where it is being drawn. A
       board opens with a turn and a slight shrink, and asking for its box
       while that is playing answers with the animation rather than the
       layout — which put the leaf a page-width out and half a page short.
       The offset properties do not lie about it. */
    var top = page.offsetTop, left = page.offsetLeft;
    if (page.offsetParent !== wrap) {
      top -= wrap.offsetTop;
      left -= wrap.offsetLeft;
    }
    leaf.style.top = top + "px";
    leaf.style.height = page.offsetHeight + "px";
    leaf.style.bottom = "auto";
    if (!twin) {
      if (dir < 0) {
        leaf.style.left = "auto";
        leaf.style.right = (wrap.clientWidth - left - page.offsetWidth) + "px";
      } else {
        leaf.style.left = left + "px";
      }
    }
    leaf.addEventListener("animationend", function () { leaf.remove(); });
    wrap.appendChild(leaf);
  }

  /* The pictures for the pages either side of this one, asked for quietly
     while somebody is looking at this one. A page that is turned to and then
     fills in has been turned to too early. */
  function warm(b, at, twin) {
    var per = b.cols * b.rows;
    var from = (twin ? (at + 1) * 2 - 1 : at + 1) * per;
    var back = (twin ? Math.max(0, at - 1) * 2 - 1 : at - 1) * per;
    [from, back].forEach(function (start) {
      for (var k = start; k < start + per * (twin ? 2 : 1); k++) {
        var slot = b.slots[k];
        if (slot && slot[2]) new Image().src = slot[2];
      }
    });
  }

  function spread(host, b, at, from) {
    var body = host.closest(".drill-body");
    /* A spread is two facing pages because that is what the binder is. On a
       phone it is two half-width pages, which is not — so the shape gives
       way to the screen and the pages are turned one at a time. */
    var twin = b.double && !narrow.matches;
    var boards = twin ? 2 : 1;
    var size = measure(body, b, boards);
    var last = twin ? Math.floor((b.pages - 1) / 2) + 1 : b.pages - 1;
    at = Math.max(0, Math.min(at, last));

    host.innerHTML = "";
    /* Both are remembered: which spread, and which page that spread starts
       on. A phone turned on its side stops being two facing pages and
       becomes one, and "spread 4" is a different place in the binder than
       it was a moment ago — the page is what somebody was actually
       looking at. */
    host.__binder = { b: b, at: at, page: twin ? Math.max(0, at * 2 - 1) : at };
    var wrap = document.createElement("div");
    wrap.className = "binder";

    if (twin) {
      wrap.appendChild(board(b, at * 2 - 1, "left", size));
      var rings = document.createElement("div");
      rings.className = "rings";
      rings.innerHTML = "<i></i><i></i><i></i><i></i>";
      wrap.appendChild(rings);
      wrap.appendChild(board(b, at * 2, "right", size));
    } else {
      wrap.appendChild(board(b, at, "right", size));
    }
    host.appendChild(wrap);

    /* The rings are inset from the top and bottom of the binder, which is
       only the same thing as being inset from the page when the page fills
       it. Measured against the page instead, so they end where it does. */
    var ring = wrap.querySelector(".rings");
    if (ring) {
      var wr = wrap.getBoundingClientRect();
      var pr = wrap.querySelector(".board").getBoundingClientRect();
      ring.style.top = (pr.top - wr.top + size.h * 0.06) + "px";
      ring.style.height = size.h * 0.88 + "px";
      ring.style.bottom = "auto";
    }

    warm(b, at, twin);

    var nav = document.createElement("div");
    nav.className = "binder-nav";
    var prev = document.createElement("button");
    prev.type = "button";
    prev.innerHTML = icon("M15 5l-7 7 7 7");
    prev.setAttribute("aria-label", "Previous page");
    prev.disabled = at <= 0;
    var pages = document.createElement("span");
    pages.className = "pages";
    /* Two facing pages are one place in the binder, so the label names both
       of them — "4-5 of 20" is where somebody is; "4 of 20" is only half
       true while page 5 is right there on the screen. */
    var right = Math.min(at * 2 + 1, b.pages);
    pages.textContent = twin
      ? (at === 0
          ? "Cover"
          : (at * 2 === right ? String(right) : at * 2 + "–" + right)
            + " of " + b.pages)
      : (at + 1) + " of " + b.pages;
    var next = document.createElement("button");
    next.type = "button";
    next.innerHTML = icon("M9 5l7 7-7 7");
    next.setAttribute("aria-label", "Next page");
    next.disabled = at >= last;
    nav.appendChild(prev);
    nav.appendChild(pages);
    nav.appendChild(next);
    host.appendChild(nav);

    /* Last, and that matters: the leaf is placed by measuring the page, and
       until the nav below it is in the document the page is not where it
       will end up. Measured too early it lands a page-width out. */
    if (from) leafOver(wrap, size, from, twin);

    /* The page is built first and the leaf laid on top of it.

       It used to be the other way round: play the animation, then build.
       Which meant the animation ended and nothing happened for as long as it
       took to measure and fill a page — a visible half second of waiting for
       a page that had already been turned. The leaf is the old page going
       over, so the new one being underneath it already is not only quicker,
       it is what is actually happening. */
    function turn(dir) {
      spread(host, b, at + dir, still ? 0 : dir);
    }
    prev.addEventListener("click", function () { turn(-1); });
    next.addEventListener("click", function () { turn(1); });
  }

  /* ------------------------------------------------- shelf and back */

  /* ------------------------------------------- the dex as a wall of slots

     The binder is the collection as its owner arranged it. This is the same
     thousand slots as a list somebody else can act on: every species, what
     is in the slot, and — the point of the whole thing — what is missing or
     standing in until something better turns up. A link to this is a want
     list that maintains itself, which is why it exists.

     Only the Pokedex gets it. Every one of its slots is a species that
     exists whether or not anybody owns it, so "missing" names a real card a
     person could go and find. A custom binder's empty pocket is not a thing
     in the world, and a filter over those would be counting nothing. */

  var GRID_FILTERS = [
    ["all", "All"],
    ["missing", "Missing"],
    ["upgrade", "Needs upgrade"],
  ];

  function gridFor(host, b) {
    host.innerHTML = "";
    var counts = { all: b.slots.length, missing: 0, upgrade: 0 };
    b.slots.forEach(function (s) {
      var st = s[5] || (s[3] ? "one" : "missing");
      if (st === "missing") counts.missing++;
      else if (st === "upgrade") counts.upgrade++;
    });

    var bar = document.createElement("div");
    bar.className = "slotbar";
    GRID_FILTERS.forEach(function (f) {
      var b2 = document.createElement("button");
      b2.type = "button";
      b2.className = "chip" + (f[0] === (host.__filter || "all") ? " active" : "");
      b2.setAttribute("data-filter", f[0]);
      b2.textContent = f[1];
      var n = document.createElement("b");
      n.textContent = counts[f[0]];
      b2.appendChild(n);
      bar.appendChild(b2);
    });
    host.appendChild(bar);

    var wall = document.createElement("div");
    wall.className = "slotwall";
    var want = host.__filter || "all";
    var shown = 0;
    b.slots.forEach(function (s, i) {
      var st = s[5] || (s[3] ? "one" : "missing");
      if (want !== "all" && st !== want) return;
      shown++;
      var cell = document.createElement("button");
      cell.type = "button";
      cell.className = "slotcell " + st;
      cell.style.setProperty("--j", i % 40);
      if (s[3] && s[2]) {
        var art = document.createElement("span");
        art.className = "art";
        art.style.backgroundImage = "url('" + s[2].replace(/'/g, "%27") + "')";
        cell.appendChild(art);
        cell.setAttribute("data-art", s[2]);
      }
      var no = document.createElement("span");
      no.className = "no";
      no.textContent = s[0];
      cell.appendChild(no);
      var nm = document.createElement("span");
      nm.className = "nm";
      nm.textContent = s[1] || "";
      cell.appendChild(nm);
      /* The detail card reads these, so a slot opens onto the same panel a
         tile anywhere else on the page does. A missing one still has a name
         and a number, which is exactly what somebody buying needs. */
      cell.setAttribute("data-title", s[1] || s[0]);
      cell.setAttribute("data-meta", s[3] ? (s[4] || s[0]) : s[0] + " · not in the binder yet");
      cell.setAttribute("data-shape", "tall");
      cell.setAttribute("data-fill", "cover");
      wall.appendChild(cell);
    });
    if (!shown) {
      var none = document.createElement("p");
      none.className = "slotnone";
      none.textContent = want === "missing"
        ? "Nothing missing — the binder is complete."
        : "Nothing waiting on an upgrade.";
      wall.appendChild(none);
    }
    host.appendChild(wall);
  }

  /* the chips, which only ever redraw the wall they belong to */
  document.addEventListener("click", function (e) {
    var chip = e.target.closest(".slotbar .chip");
    if (!chip) return;
    var host = chip.closest(".slotgrid");
    if (!host || !host.__binder) return;
    host.__filter = chip.getAttribute("data-filter");
    gridFor(host, host.__binder);
  });

  function show(drill, what) {
    var rail = drill.querySelector(".shelf") || drill.querySelector(".binder-rail");
    var loose = drill.querySelector(".loose");
    var sp = drill.querySelector(".spread");
    var grid = drill.querySelector(".slotgrid");
    var views = drill.querySelector(".viewpick");
    if (rail) rail.hidden = what !== "rail";
    if (loose) loose.hidden = what !== "loose";
    if (sp) sp.hidden = what !== "binder";
    if (grid) grid.hidden = what !== "grid";
    // the Binder/List switch belongs to the two views it switches between
    if (views) views.hidden = !(what === "binder" || what === "grid");
    var back = drill.querySelector(".drill-head .back");
    if (back) back.hidden = what === "rail";
  }

  document.addEventListener("click", function (e) {
    var drill = e.target.closest(".drill");
    if (!drill) return;

    if (e.target.closest(".drill-head .back")) {
      show(drill, "rail");
      /* out of the binder and back onto the shelf of them, which is the
         collection's own address again */
      address(scopeOf(drill));
      var crumb = drill.querySelector(".crumb");
      if (crumb) crumb.textContent = crumb.getAttribute("data-was") || "";
      return;
    }

    var box = e.target.closest(".tcgbox");
    if (box) {
      show(drill, "loose");
      return;
    }

    /* the Binder / List switch, for a binder already open */
    var view = e.target.closest(".viewpick .chip");
    if (view) {
      var want = view.getAttribute("data-view");
      drill.querySelectorAll(".viewpick .chip").forEach(function (c) {
        c.classList.toggle("active", c === view);
      });
      show(drill, want);
      return;
    }

    var sp = e.target.closest(".binder-spine");
    if (!sp) return;
    var host = drill.querySelector(".spread");
    if (!host) {
      host = document.createElement("div");
      host.className = "spread";
      drill.querySelector(".drill-body").appendChild(host);
    }
    host.innerHTML = "";
    show(drill, "binder");
    /* One binder open is one of the two addresses cards has beyond its own:
       the dex has its own name, everything else is the binders shelf. */
    address(sp.getAttribute("data-kind") === "dex" ? "pokedex" : "binders");
    var crumb = drill.querySelector(".crumb");
    if (crumb && !crumb.getAttribute("data-was")) {
      crumb.setAttribute("data-was", crumb.textContent);
    }
    fetchBinder(sp.getAttribute("data-binder"), function (b) {
      if (crumb) {
        crumb.textContent = b.name + " · " + b.cols + "x" + b.rows
          + " pockets · " + b.filled + " of " + b.total;
      }
      spread(host, b, 0);

      /* The Pokedex gets a second way of being read: the same slots as a
         list, filtered down to what is missing or standing in. Built here
         rather than on demand because the payload is already in hand and a
         thousand cells cost less than the fetch that brought them. */
      var grid = drill.querySelector(".slotgrid");
      var pick = drill.querySelector(".viewpick");
      if (b.kind === "dex") {
        if (!grid) {
          grid = document.createElement("div");
          grid.className = "slotgrid";
          drill.querySelector(".drill-body").appendChild(grid);
        }
        if (!pick) {
          pick = document.createElement("div");
          pick.className = "viewpick";
          [["binder", "Binder"], ["grid", "List"]].forEach(function (v, i) {
            var c = document.createElement("button");
            c.type = "button";
            c.className = "chip" + (i === 0 ? " active" : "");
            c.setAttribute("data-view", v[0]);
            c.textContent = v[1];
            pick.appendChild(c);
          });
          drill.querySelector(".drill-head").insertBefore(
            pick, drill.querySelector(".drill-head .spacer")
          );
        }
        grid.__binder = b;
        grid.__filter = grid.__filter || "all";
        gridFor(grid, b);
        pick.querySelectorAll(".chip").forEach(function (c) {
          c.classList.toggle("active", c.getAttribute("data-view") === "binder");
        });
        /* Said again now that both boxes exist. show() ran before the list
           was built — it is built from the payload, which arrives later —
           so the switch had nothing to hide, and a freshly appended element
           is visible by default. That is how the binder and the list ended
           up drawn on top of one another. */
        show(drill, "binder");
      } else {
        if (grid) grid.hidden = true;
        if (pick) pick.hidden = true;
      }
    });
  });

  /* A binder is measured against the box it is drawn in, so it has to be
     measured again when that box changes shape. */
  var redraw;
  function again() {
    clearTimeout(redraw);
    redraw = setTimeout(function () {
      var d = document.querySelector(".drill.on");
      if (d) place(d);
      var host = d && d.querySelector(".spread:not([hidden])");
      var was = host && host.__binder;
      if (was) {
        var twin = was.b.double && !narrow.matches;
        spread(host, was.b, twin ? Math.floor((was.page + 1) / 2) : was.page);
      }
    }, 180);
  }
  window.addEventListener("resize", again);
  /* And the crossing itself, which is the thing that actually matters here:
     a phone turned on its side changes which side of 700px the page is on,
     and that decides where the layer lives, not only how big it is. */
  if (narrow.addEventListener) narrow.addEventListener("change", again);

  /* ------------------------------------------------- arriving focused

     A link that names one shelf — /u/<name>/games, /u/<name>/pokedex —
     lands here with that shelf already decided, and opens it rather than
     making somebody find the right piece of furniture first.

     The server has already checked that the shelf is published and that
     this profile gets a room at all; a name that survives that and still
     matches nothing here simply leaves the room as it is, which is the
     right answer for a link to a binder somebody has since put away.

     Deliberately after every listener above is bound, and deliberately not
     a redirect or a separate page: the room is the same document either
     way, so the back button goes back to wherever the visitor came from
     and the page still reads with scripting off. */
  var focus = room.getAttribute("data-focus");
  if (focus) {
    var wanted = focus === "pokedex" || focus === "binders" ? "cards" : focus;
    var layer = document.getElementById("drill-" + wanted);
    if (layer) {
      openDrill(layer);
      if (focus === "pokedex") {
        /* One binder in particular. Found by kind rather than by id or by
           name: the id is nobody's business outside the server and the name
           is whatever its owner called it. */
        var dex = layer.querySelector('.binder-spine[data-kind="dex"]');
        if (dex) dex.click();
      }
    }
  }
  /* Arrived. From here the address follows the room rather than the link. */
  settling = false;
})();
