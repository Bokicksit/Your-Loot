import { Link, useNavigate } from "react-router-dom";
import { BrandMark, Icon } from "../components/Icons.jsx";

/** What somebody sees before they have an account.
 *
 *  Only on an install that offers accounts to anybody — see SignIn.jsx. A
 *  self-hosted server has one household on it and no one to persuade, so it
 *  goes straight to the app the way it always has.
 *
 *  Everything claimed here is a thing the app does today. Nothing about
 *  games, films or comics: those catalogues forbid commercial use, this
 *  service does not carry them, and advertising a collection that is not
 *  there is how a first visit becomes the last one.
 */

const SHELVES = [
  { icon: "card", title: "Trading cards", body: "Every card, every set, every printing — and the Pokédex all 1,025 of them fit into." },
  { icon: "vinyl", title: "Records", body: "Scan the sleeve. Pressing, label, catalogue number and country, filled in for you." },
  { icon: "book", title: "Books", body: "Scan the ISBN on the back. Author, edition, page count and jacket." },
  { icon: "brick", title: "LEGO", body: "Sets and minifigs, with the piece counts and the year it came out." },
];

const CRAFT = [
  {
    title: "Binders that work like binders",
    body:
      "A Pokédex where each slot waits for whichever card you like best. A set binder that fills as you find them. Or a custom one, in whatever order you decide — because a shelf is a thing you arrange, not a list somebody sorted for you.",
  },
  {
    title: "Master sets, down to the printing",
    body:
      "Not “Charizard”. Charizard, reverse holo, Poké Ball pattern. The booklet that comes in the box has a box for each one, and so does this — 476 slots for a set of 180 cards, because that is genuinely how many there are.",
  },
  {
    title: "Point your camera at the barcode",
    body:
      "Records and books resolve from the barcode already on them. No typing, no picking the wrong edition out of a list of nine.",
  },
  {
    title: "Your collection leaves whenever you like",
    body:
      "One file with every item, every copy, every note and every photograph. Not an export request, not a queue — a button, and then it is yours. It is the promise everything else here rests on.",
  },
];

export default function LandingPage() {
  const navigate = useNavigate();
  const go = () => navigate("/signin");

  return (
    <div className="landing">
      <header className="landing-bar">
        <span className="landing-logo">
          <BrandMark size={22} />
          Your <b>Loot</b>
        </span>
        <button type="button" className="ghost" onClick={go}>
          Sign in
        </button>
      </header>

      <section className="landing-hero">
        <h1>
          You already own it.
          <br />
          <em>Now you can find it.</em>
        </h1>
        <p className="landing-sub">
          A home for the things you collect — what you have, what you're
          missing, and which shelf it's on. The software is free and has no
          limits at all; you can run it on your own machine today. This is us
          running it for you instead.
        </p>
        <div className="landing-cta">
          <button type="button" className="primary" onClick={go}>
            <Icon id="check" />
            Start with your cards — free
          </button>
          <button type="button" className="ghost" onClick={go}>
            Sign in
          </button>
        </div>
        <p className="landing-fine">
          No card needed to start. Nothing is advertised at you and nothing
          about you is sold — the subscription is the only way this pays for
          itself, which is rather the point.
        </p>
      </section>

      <section className="landing-shelves">
        {SHELVES.map((s) => (
          <div className="landing-shelf" key={s.title}>
            <Icon id={s.icon} />
            <h3>{s.title}</h3>
            <p>{s.body}</p>
          </div>
        ))}
      </section>

      <section className="landing-craft">
        <h2>Built by somebody who collects</h2>
        {CRAFT.map((c) => (
          <div className="landing-point" key={c.title}>
            <h3>{c.title}</h3>
            <p>{c.body}</p>
          </div>
        ))}
      </section>

      <section className="landing-tiers">
        <h2>What it costs</h2>
        <div className="landing-plans">
          <div className="landing-plan">
            <h3>Free here</h3>
            <p className="landing-price">$0</p>
            <p className="landing-plan-lead">Enough to keep a real collection.</p>
            <ul>
              <li>300 cards</li>
              <li>The first 151 of the Pokédex</li>
              <li>One binder besides it — custom or a master set</li>
              <li>Wanted list, tags, notes and barcode scanning</li>
              <li>Export everything, whenever, in one file</li>
            </ul>
          </div>
          <div className="landing-plan lit">
            <h3>Supporter</h3>
            <p className="landing-price">
              $4<span>/month</span>
            </p>
            <p className="landing-plan-lead">The lid comes off, and the other shelves open.</p>
            <ul>
              <li>Cards without a limit</li>
              <li>All 1,025 Pokédex slots, and every binder you want</li>
              <li>Records, books and LEGO</li>
              <li>New collections as they arrive, at the price you joined at</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="landing-open">
        <h2>Or run it yourself, with no limits at all</h2>
        <p>
          Your Loot is open source under the AGPL, and the limits above exist
          nowhere but here. Put it on a machine of your own — a spare box, a
          NAS, a five-dollar server — and you get every card, all 1,025
          Pokédex slots and as many binders as you like, free, for good.
          It's a container and a database; if you've set up anything
          self-hosted before, it's an evening.
        </p>
        <p>
          What you're paying for on this site is not the software. It's
          somebody else running it: a server, a database, a disk full of your
          photographs, and a bill at the end of every month whether anybody
          subscribes or not. If you'd rather not deal with that, four dollars
          is us dealing with it. If you would, the door's open and there's
          nothing behind it.
        </p>
        <a className="landing-repo" href="https://github.com/Bokicksit/Your-Loot">
          <Icon id="link" />
          Run your own copy
        </a>
      </section>

      <footer className="landing-foot">
        <span>© 2026 Your Loot</span>
        <Link to="/privacy">Privacy</Link>
        <Link to="/terms">Terms</Link>
        <Link to="/delete-account">Delete your account</Link>
      </footer>
    </div>
  );
}
