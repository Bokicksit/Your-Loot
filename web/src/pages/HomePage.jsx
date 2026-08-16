import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import {
  MODULES,
  useAvailableModules,
  useEnabledModules,
  useSettings,
} from "../settings.jsx";
import { DEFAULT_TAGLINE, pickTagline } from "../taglines.js";

const PATHS = {
  cards: "/cards", games: "/games", hardware: "/hardware",
  movies: "/movies", books: "/books", records: "/records",
  lego: "/lego", comics: "/comics",
};
// small numbers read better as words; past a dozen they stop being a count
// you can see at a glance and become a figure
const WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
               "Eight", "Nine", "Ten", "Eleven", "Twelve"];
const UNIT = {
  cards: "card", games: "title", hardware: "item", movies: "disc", books: "book",
  records: "record", lego: "set", comics: "issue",
};

export default function HomePage() {
  const { settings } = useSettings();
  const enabled = useEnabledModules();
  // what this server carries, which is what "more to turn on" must count
  const available = useAvailableModules();
  const [stats, setStats] = useState(null);
  // Chosen once settings are known, so the category lines can join in — and
  // held for the session, so navigating back here doesn't reshuffle it.
  const [tagline, setTagline] = useState(DEFAULT_TAGLINE);

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
  }, []);

  const enabledKeys = enabled.map((m) => m.key).join(",");
  useEffect(() => {
    if (enabledKeys) setTagline(pickTagline(enabledKeys.split(",")));
  }, [enabledKeys]);

  // On or off, and nothing in between. Starring used to be a second, quieter
  // switch that decided the same thing, which meant a collection could be
  // turned on and still be nowhere — so it's gone, and this list is simply
  // what Settings says you collect.
  const shown = enabled;
  // Against what this server carries, not against every collection the code
  // knows how to draw. A service offering four said "4 more to turn on in
  // settings" — pointing at four that are not there and cannot be turned on.
  const hidden = available.length - enabled.length;
  // Named rather than counted: "Records, Books and LEGO" tells somebody what
  // they would get, where "three more collections" tells them nothing.
  const paidNames = available
    .filter((m) => (settings?.paid_modules || []).includes(m.key))
    .map((m) => m.label);
  // Hardware used to borrow the games count, because the API had no hardware
  // number to give — so a shelf with one console read "29 items". It reports
  // both separately now, and this asks for what it means.
  const count = (key) => (stats?.[key] ? stats[key].items : null);

  // "Eight shelves · 1,043 things" — the two numbers that say how much there
  // is, under the line that says what it is. Words for the small number
  // because eight shelves reads better than 8, numerals for the big one
  // because nobody wants "one thousand and forty-three".
  const totalThings = shown.reduce((n, m) => n + (count(m.key) || 0), 0);
  const shelfWord = WORDS[shown.length] || shown.length;

  return (
    <div className="home">
      <h2>{tagline}</h2>
      {stats && (
        <p className="home-sub">
          {shelfWord} {shown.length === 1 ? "shelf" : "shelves"}
          {totalThings > 0 && <> · {totalThings.toLocaleString()} things</>}
        </p>
      )}

      <div className="home-tiles">
        {shown.map((m) => (
          <Link key={m.key} to={PATHS[m.key]} className="home-tile">
            <Icon id={m.icon} />
            <strong>{m.label}</strong>
            {count(m.key) != null && (
              <small>
                {count(m.key)} {UNIT[m.key]}
                {count(m.key) === 1 ? "" : "s"}
              </small>
            )}
          </Link>
        ))}

      </div>

      {/* Only worth saying when something is actually missing. A line telling
          you about collections you already have is noise on every visit. */}
      {settings && hidden > 0 && (
        <p className="home-hint">
          <Icon id="sliders" />
          <span>
            {hidden} more {hidden === 1 ? "collection" : "collections"} to turn
            on in <Link to="/settings">Settings</Link>.
          </span>
        </p>
      )}

      {/* At the bottom, after the shelves, and only where this server
          actually charges for something. A free install has no paid_modules
          and therefore never sees it — nobody self-hosting should be sold
          anything by their own server. */}
      {settings && !settings.subscribed && paidNames.length > 0 && (
        <section className="home-upsell">
          <div>
            <strong>Add your other shelves</strong>
            <p>
              {paidNames.join(", ")} for $4 a month, and no limit on cards or
              binders. Or run your own copy, where there are no limits at all.
            </p>
          </div>
          <Link to="/settings" className="primary">
            <Icon id="star" />
            See Supporter
          </Link>
        </section>
      )}

      {/* `settings &&` because the list is empty until the server answers,
          and "No collections turned on" flashing at somebody who has eight
          is the same lie as the one above, in the other direction. */}
      {settings && shown.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="sliders" /></span>
          <strong>No collections turned on</strong>
          <p>Pick what you collect and it'll show up here.</p>
          <Link to="/settings" className="primary">Open settings</Link>
        </div>
      )}
    </div>
  );
}
