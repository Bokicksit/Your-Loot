import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BrandMark, Icon } from "../components/Icons.jsx";

/** What somebody sees before they have an account.
 *
 *  Only on an install that offers accounts to anybody — see SignIn.jsx. A
 *  self-hosted server has one household on it and no one to persuade, so it
 *  goes straight to the app the way it always has.
 *
 *  The layout is the design system's home page: the Pokédex wall fills as
 *  you scroll, the binder configurator is live, and the three routes in are
 *  laid side by side. The copy is not the design's, deliberately — every
 *  claim on this page is checked against what the app actually does. Nothing
 *  about games, films or comics: those catalogues aren't carried here, and
 *  advertising a collection that is not there is how a first visit becomes
 *  the last one. Prices and limits match Settings, not the mock.
 */

const REPO = "https://github.com/Bokicksit/Your-Loot";

// Gen I — the 151 the free tier opens with, and a wall that fits a hero.
const DEX_TOTAL = 151;

/** Real cards, not swatches: the "151" set's card numbers 1–151 are the
 *  National dex in order, so the wall can fill with Bulbasaur through Mew
 *  as printed. Served from TCGdex, whose assets are published under MIT for
 *  exactly this use — the same host the app's own catalogue art sits on —
 *  at the small size, about 14KB a card. An image only renders once its
 *  slot lights up, so a visitor who never scrolls never downloads the set. */
const cardArt = (n) =>
  `https://assets.tcgdex.net/en/sv/sv03.5/${String(n).padStart(3, "0")}/low.webp`;

// the same hashed-art palette the collector's room draws with
const ART = [
  "#c9a94a", "#7fb3d5", "#d98b6a", "#8fd0a8", "#b79ad6",
  "#e0c37a", "#6fa8a0", "#d97f8f", "#9ec46f", "#8ab6d6",
];

// the swatches the real binder settings offer
const COVERS = [
  ["Red", "#c0392b"], ["Orange", "#e08a1e"], ["Yellow", "#e0c02b"],
  ["Green", "#3fa055"], ["Teal", "#2f9d9d"], ["Blue", "#3a6fd0"],
  ["Purple", "#8a5cd0"], ["Pink", "#d05a9a"], ["Grey", "#6b7280"],
  ["Black", "#1f2026"],
];

/** The dex wall fills as you scroll — a collection being kept, compressed
 *  into the time the wall is in front of you.
 *
 *  Where "in front of you" is depends on the layout, which is why this asks
 *  two different questions. Wide, the case sits in the hero beside the
 *  headline and is on screen from the first frame, so page scroll is the
 *  honest measure: you arrive, you scroll, it fills.
 *
 *  Stacked, it is underneath the hero text — five hundred pixels of scrolling
 *  happen before any of it is visible, and driving the fill from page scroll
 *  meant the first row was already at forty-five by the time you could see
 *  it. Nothing appeared to happen, because it had all happened above the
 *  fold. So on a narrow screen the fill is driven by the case's own travel
 *  through the viewport: the cards light up as they arrive, rather than
 *  arriving lit.
 */
function useScrollFill(caseRef) {
  const [fill, setFill] = useState(8);
  useEffect(() => {
    let raf = 0;
    const read = () => {
      const vh = window.innerHeight || 800;
      const el = caseRef.current;
      // the same 840px the stylesheet stacks the hero at
      const stacked = (window.innerWidth || 1280) < 840;
      let p;
      if (stacked && el) {
        // Measured against the wall itself, and against a line three
        // quarters down the screen rather than the very bottom: the row
        // being lit is then a little above the fold, so rows arrive dark
        // and light up as you carry on — which is the thing worth watching.
        const r = el.getBoundingClientRect();
        p = (vh * 0.75 - r.top) / r.height;
      } else {
        const y = window.scrollY || document.documentElement.scrollTop || 0;
        p = y / (vh * 1.05);
      }
      p = Math.max(0, Math.min(1, p));
      setFill(Math.max(8, Math.min(100, Math.round(8 + p * 94))));
    };
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        read();
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    read();
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [caseRef]);
  return fill;
}

/** Sections rise in as they arrive. The hero carries .in from the first
 *  render instead — the top of the page must not wait for an observer. */
function useReveals(rootRef) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root || !window.IntersectionObserver) {
      root?.querySelectorAll(".rv").forEach((el) => el.classList.add("in"));
      return;
    }
    const io = new IntersectionObserver(
      (es) =>
        es.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        }),
      { threshold: 0.16 }
    );
    root.querySelectorAll(".rv:not(.in)").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [rootRef]);
}

export default function LandingPage() {
  const navigate = useNavigate();
  const go = () => navigate("/signin");
  const rootRef = useRef(null);
  useReveals(rootRef);

  const caseRef = useRef(null);
  const fill = useScrollFill(caseRef);
  const owned = Math.round(DEX_TOTAL * Math.min(1, fill / 100));

  const [across, setAcross] = useState(4);
  const [down, setDown] = useState(4);
  const [cover, setCover] = useState(0);
  const per = across * down;
  const pages = Math.ceil(DEX_TOTAL / per);

  return (
    <div className="lp" id="top" ref={rootRef}>
      <nav className="lp-nav">
        <span className="brand">
          <BrandMark size={22} />
          Your <em>Loot</em>
        </span>
        <span className="links">
          <a href="#top">Pokédex</a>
          <a href="#binders">Binders</a>
          <a href="#everything">Everything else</a>
          <a href="#get">Get it</a>
        </span>
        <span className="sp" />
        <button type="button" className="btn line sm" onClick={go}>
          Sign in
        </button>
        <button type="button" className="btn gold sm" onClick={go}>
          Start free
        </button>
      </nav>

      <header className="lp-hero">
        <div className="lp-wrap hero-grid">
          <div>
            <span className="eyebrow rv in">
              <Icon id="card" />
              Pokémon TCG · and everything else you keep
            </span>
            <h1 className="rv in d1">
              Build the binder. <em>Send the link.</em>
            </h1>
            <p className="lp-lede rv in d2">
              A slot for every Pokémon, binders of your own for everything
              else, and a page you can hand to a friend. Free and open source
              — or let us host it.
            </p>
            <div className="lp-cta rv in d3">
              <button type="button" className="btn gold" onClick={go}>
                <Icon id="cloud" />
                Start a collection — free
              </button>
              <a className="btn line" href={REPO}>
                <Icon id="term" />
                Self-host it instead
              </a>
              <span className="note">No card needed · leaves in one file</span>
            </div>
          </div>

          <div className="rv in d1">
            <div className="lp-head" style={{ marginBottom: 18 }}>
              <span className="kicker">The Pokédex</span>
              <h2 style={{ fontSize: 26 }}>
                Every set. Every printing. One slot per Pokémon.
              </h2>
              <p style={{ fontSize: 14 }}>
                The dex is the spine of the app: one numbered slot per
                Pokémon, and behind each slot every printing that exists —
                base, promo, reverse, illustration rare. File the one you
                actually own and the slot lights up.
              </p>
            </div>
            <div className="dexcase rv in d2">
              <div className="bar">
                <strong>Pokédex</strong>
                <span className="scroll-hint">Gen I · scroll to fill</span>
                <span className="count">
                  {owned} / {DEX_TOTAL}
                </span>
              </div>
              <div className="meter">
                <i
                  style={{
                    width: `${Math.min(100, (owned / DEX_TOTAL) * 100).toFixed(1)}%`,
                  }}
                />
              </div>
              <div className="dexwall" ref={caseRef}>
                {Array.from({ length: DEX_TOTAL }, (_, i) => (
                  <span
                    key={i}
                    className={i < owned ? "dexslot got" : "dexslot"}
                    style={{ color: ART[i % ART.length] }}
                  >
                    {/* The hashed colour stays behind it as the loading
                        state, so a slow image still reads as a filled slot.
                        Not loading="lazy": an image only exists once its
                        slot lights up, so the conditional render is already
                        the laziness, and everything that mounts is on
                        screen by definition. */}
                    {i < owned && (
                      <img src={cardArt(i + 1)} alt="" decoding="async" />
                    )}
                    <span className="no">{i + 1}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="lp-band alt" id="binders">
        <div className="lp-wrap">
          <div className="lp-head rv">
            <span className="kicker">Binders</span>
            <h2>Binders built the way yours are built.</h2>
            <p>
              Pick the pocket grid, pick the cover, name it, and the app lays
              your cards out exactly as they sit on your shelf — page by
              page, facing pages together. Set it up here and watch the pages
              change.
            </p>
          </div>
          <div className="lab rv d1">
            <div>
              <div className="field">
                <span className="label">Pockets across</span>
                <div className="stepper">
                  <button type="button" onClick={() => setAcross((v) => Math.max(2, v - 1))}>
                    −
                  </button>
                  <span className="val">{across}</span>
                  <button type="button" onClick={() => setAcross((v) => Math.min(5, v + 1))}>
                    +
                  </button>
                </div>
              </div>
              <div className="field">
                <span className="label">Pockets down</span>
                <div className="stepper">
                  <button type="button" onClick={() => setDown((v) => Math.max(2, v - 1))}>
                    −
                  </button>
                  <span className="val">{down}</span>
                  <button type="button" onClick={() => setDown((v) => Math.min(5, v + 1))}>
                    +
                  </button>
                </div>
              </div>
              <div className="field">
                <span className="label">Cover</span>
                <div className="swatches">
                  {COVERS.map(([name, hex], i) => (
                    <button
                      key={name}
                      type="button"
                      className={i === cover ? "on" : ""}
                      style={{ color: hex }}
                      title={name}
                      onClick={() => setCover(i)}
                    />
                  ))}
                </div>
              </div>
              <p className="hint">
                {per} a page · {pages} pages for a Gen I run. Change it later
                and nothing moves out of place.
              </p>
            </div>
            <div className="binder-demo">
              <div className="cover" style={{ color: COVERS[cover][1] }}>
                <div
                  className="page"
                  style={{ gridTemplateColumns: `repeat(${across}, minmax(0, 1fr))` }}
                >
                  {Array.from({ length: per }, (_, i) => (
                    <i
                      key={`${across}x${down}-${i}`}
                      className={(i * 7) % 5 === 3 ? "gap" : ""}
                      style={{ color: ART[(i + cover) % ART.length] }}
                    />
                  ))}
                </div>
              </div>
              <span className="caption">
                {COVERS[cover][0]} · {across}×{down} · {per} a page
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-band" id="everything">
        <div className="lp-wrap">
          <div className="lp-head rv">
            <span className="kicker">Everything else</span>
            <h2>Cards are the hard part. The rest is already here.</h2>
            <p>
              Same app, same export, same shareable page — for whatever else
              ends up on your shelves. amiibo arrive with the whole line
              catalogued: all 932 figures and cards, searchable by character
              or series, each copy marked new-in-box, boxed or loose.
            </p>
          </div>
          <div className="strip rv d1">
            <span className="chip2">
              <Icon id="fig" />
              amiibo
            </span>
            <span className="chip2">
              <Icon id="vinyl" />
              Records
            </span>
            <span className="chip2">
              <Icon id="book" />
              Books
            </span>
            <span className="chip2">
              <Icon id="brick" />
              LEGO sets
            </span>
          </div>
        </div>
      </section>

      <section className="lp-band alt" id="get">
        <div className="lp-wrap">
          <div className="lp-head rv">
            <span className="kicker">Three ways in</span>
            <h2>Run it yourself, or let us run it.</h2>
            <p>
              The software is the same everywhere; what changes is who runs
              the server. Whichever you choose, your collection leaves in one
              file whenever you want it.
            </p>
          </div>
          <div className="routes">
            <div className="route rv">
              <div className="top">
                <h3>Self-host</h3>
                <span className="flag">Open source</span>
              </div>
              <div className="tier-price">
                Free<small>forever</small>
              </div>
              <p>
                Your server, your database, your photos. One command and it's
                up.
              </p>
              <code>docker compose up -d</code>
              <ul>
                <li>
                  <Icon id="check" />
                  <span>Everything, with no limits at all</span>
                </li>
                <li>
                  <Icon id="check" />
                  <span>All 1,025 Pokédex slots and unlimited binders</span>
                </li>
                <li>
                  <Icon id="check" />
                  <span>Backups as a single zip</span>
                </li>
              </ul>
              <a className="btn line" href={REPO}>
                <Icon id="term" />
                Read the setup
              </a>
            </div>

            <div className="route pick rv d1">
              <div className="top">
                <h3>Hosted</h3>
                <span className="flag">Most people</span>
              </div>
              <div className="tier-price">
                Free<small>no card</small>
              </div>
              <p>
                We keep it running and updated. Enough to keep a real
                collection, honestly sized.
              </p>
              <ul>
                <li>
                  <Icon id="check" />
                  <span>300 cards and the first 151 of the Pokédex</span>
                </li>
                <li>
                  <Icon id="check" />
                  <span>A binder besides it — custom or a master set</span>
                </li>
                <li>
                  <Icon id="check" />
                  <span>amiibo and records — full catalogues, wanted list, a public page</span>
                </li>
              </ul>
              <button type="button" className="btn gold" onClick={go}>
                <Icon id="cloud" />
                Start a collection
              </button>
            </div>

            <div className="route rv d2">
              <div className="top">
                <h3>Supporter</h3>
                <span className="flag">Optional</span>
              </div>
              <div className="tier-price">
                $4<small>/ month</small>
              </div>
              <p>
                Pays for the servers and keeps the free tier free. Cancel
                whenever; nothing you made is deleted.
              </p>
              <ul>
                <li>
                  <Icon id="heart" />
                  <span>Keeps the project going</span>
                </li>
                <li>
                  <Icon id="check" />
                  <span>All 1,025 slots, cards and binders without limits</span>
                </li>
                <li>
                  <Icon id="check" />
                  <span>Books and LEGO shelves</span>
                </li>
                <li>
                  <Icon id="check" />
                  <span>The collector's room on your public page</span>
                </li>
              </ul>
              <button type="button" className="btn line" onClick={go}>
                <Icon id="heart" />
                Chip in
              </button>
            </div>
          </div>
        </div>
      </section>

      <footer className="lp-foot">
        <div className="lp-wrap in">
          <span className="brand" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <BrandMark size={17} />
            Your Loot
          </span>
          <span className="sp" />
          <Link to="/help">How it works</Link>
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
          <Link to="/delete-account">Delete your account</Link>
          <a href={REPO}>Source</a>
          <span>Open source · your data exports in one file</span>
        </div>
      </footer>
    </div>
  );
}
