/* The public profile's own behaviour. Kept out of the Python because a
   page rendered from an f-string turns every brace in a script into a pair,
   and a script nobody can read is a script nobody will fix.

   Everything here is an addition to a page that already works without it.
   A crawler, or a browser with scripting off, gets the items. */

/* The grid is visible without this. `rv` is added by script precisely so
   that a browser with no JavaScript — or a crawler — sees the items rather
   than a page of things waiting to be faded in. */
(function () {
  var items = document.querySelectorAll(".pub-item");
  if (!window.IntersectionObserver || !items.length) return;
  for (var i = 0; i < items.length; i++) items[i].classList.add("rv");
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    });
  }, { threshold: 0.12 });
  for (var j = 0; j < items.length; j++) io.observe(items[j]);
})();
/* The room scrolls sideways on its own — a touch screen and a trackpad both
   already do this, and the scrollbar is hidden rather than absent. This adds
   the one gesture that would otherwise be missing, dragging with a mouse,
   and puts the hint away once somebody has looked.

   And it goes round. A room with a wall at each end is a strip of furniture;
   a room you can keep walking through is a room. Past the last collection
   the next one along is the first, and before the first is the last.

   Done by standing three copies of the strip side by side and keeping the
   view in the middle one: when the scroll drifts a whole strip's width away
   from where it started, it is put back by exactly that width. The copies
   are identical, so the frame it lands on is the frame it left — there is
   nothing to see, which is the point. */
(function () {
  var room = document.querySelector(".room2");
  var scene = room && room.querySelector(".scene");
  var strip = scene && scene.querySelector(".scene-strip");
  if (!strip) return;

  var span = 0;
  function loop() {
    /* Nothing to go round if it all fits — a room with three zones on a
       wide screen has no end to reach. */
    if (scene.scrollWidth <= scene.clientWidth + 4) return;
    if (strip.dataset.looped) return;
    strip.dataset.looped = "1";

    var before = strip.cloneNode(true);
    var after = strip.cloneNode(true);
    [before, after].forEach(function (copy) {
      copy.setAttribute("aria-hidden", "true");
      copy.querySelectorAll(".zone").forEach(function (z) {
        z.setAttribute("tabindex", "-1");   /* the keyboard visits one of each */
      });
    });
    scene.insertBefore(before, strip);
    scene.appendChild(after);
    /* The stylesheet asks for smooth scrolling, which is right for a jump
       somebody asked for and wrong for this one: the correction would be
       animated, and a whole strip gliding backwards is the seam this exists
       to hide. */
    scene.style.scrollBehavior = "auto";
    span = strip.getBoundingClientRect().width + parseFloat(getComputedStyle(scene).gap || 0);
    scene.scrollLeft = span;
  }

  function keep() {
    if (!span) return;
    /* Half a strip either side of the middle is how far somebody can move
       before anything is moved under them. */
    var shift = 0;
    if (scene.scrollLeft < span * 0.5) shift = span;
    else if (scene.scrollLeft > span * 1.5) shift = -span;
    if (!shift) return;
    scene.scrollLeft += shift;
    /* A drag is measured from where the scroll stood when it began, and
       that mark has just moved. */
    l0 += shift;
  }

  loop();
  var redo;
  window.addEventListener("resize", function () {
    clearTimeout(redo);
    redo = setTimeout(function () {
      if (span) {
        span = strip.getBoundingClientRect().width
          + parseFloat(getComputedStyle(scene).gap || 0);
      } else {
        loop();
      }
    }, 200);
  });

  /* Pressing is not yet dragging.

     This used to take the pointer on pointerdown, which quietly cost the
     mouse every click in the room: while an element holds the pointer, the
     browser aims the click that follows at *it* rather than at whatever is
     under the cursor, so every handler asking `e.target.closest(".zone")`
     got the scene and gave up. Touch never saw it — touch returns above,
     the browser pans it — which is why the room worked on a phone and only
     scrolled on a desktop.

     So the capture waits for movement. A press that goes nowhere is a click
     and is left entirely alone; once the cursor has travelled far enough to
     mean it, the drag takes over and the capture happens then, which is also
     the point at which it starts being useful — it is what keeps the pan
     alive when the cursor runs off the edge. */
  var SLOP = 4;   /* px of travel before a press is a drag rather than a click */

  var down = false, dragging = false, swallow = false, x0 = 0, l0 = 0, id = 0;
  scene.addEventListener("scroll", function () {
    room.classList.add("panned");
    keep();
  });
  scene.addEventListener("pointerdown", function (e) {
    if (e.pointerType === "touch") return;   // the browser does this one
    if (e.button !== 0) return;              // a right-click is not a grab
    down = true; dragging = false; id = e.pointerId;
    x0 = e.clientX; l0 = scene.scrollLeft;
  });
  scene.addEventListener("pointermove", function (e) {
    if (!down) return;
    var dx = e.clientX - x0;
    if (!dragging) {
      if (Math.abs(dx) < SLOP) return;       /* still just a press */
      dragging = true;
      /* throws if the pointer is no longer live, which is not worth failing
         a pan over */
      try { scene.setPointerCapture(id); } catch (err) {}
      scene.style.cursor = "grabbing";
    }
    scene.scrollLeft = l0 - dx;
  });
  function up() {
    /* A drag ends in a click the browser owes us, and it is not one anybody
       made — without this, letting go over a zone opens it. */
    if (dragging) {
      swallow = true;
      setTimeout(function () { swallow = false; }, 0);
    }
    down = false; dragging = false; scene.style.cursor = "";
  }
  scene.addEventListener("pointerup", up);
  scene.addEventListener("pointercancel", up);
  document.addEventListener("click", function (e) {
    if (!swallow) return;
    swallow = false;
    e.stopPropagation();
    e.preventDefault();
  }, true);
})();
