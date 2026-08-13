import { useEffect, useState } from "react";
import { Icon } from "./Icons.jsx";

/* A screen at a time, without dragging.
 *
 * A shelf of four hundred items is a long scroll on a phone, and flicking
 * through it loses your place. These move exactly one viewport — far enough to
 * be worth pressing, short enough that you can still see where you came from.
 *
 * Deliberately small and out of the way. They are a convenience on a long
 * page, not a navigation control, so they only appear once there is more than
 * a screen to move through, and the up arrow only once you have left the top.
 */
export default function PageArrows() {
  const [state, setState] = useState({ show: false, atTop: true });

  useEffect(() => {
    const read = () => {
      const doc = document.documentElement;
      const room = doc.scrollHeight - window.innerHeight;
      setState({
        // one screen of slack before they are worth offering at all
        show: room > window.innerHeight * 0.6,
        atTop: window.scrollY < 40,
        atEnd: window.scrollY > room - 40,
      });
    };
    read();
    window.addEventListener("scroll", read, { passive: true });
    window.addEventListener("resize", read);
    // the list loads after mount and the page grows underneath us
    const t = setInterval(read, 800);
    return () => {
      window.removeEventListener("scroll", read);
      window.removeEventListener("resize", read);
      clearInterval(t);
    };
  }, []);

  if (!state.show) return null;

  // a little less than a full screen, so a row is never stepped clean over
  const page = () => Math.round(window.innerHeight * 0.9);
  // Instant, not smooth. A smooth scroll is a nicety that silently does
  // nothing wherever the browser has animation turned down — and a button
  // that sometimes moves the page and sometimes appears dead is worse than
  // one that always jumps. Landing a screen further on is the whole job.
  const go = (dir) => window.scrollBy({ top: dir * page(), behavior: "auto" });

  return (
    <div className="page-arrows" aria-hidden="false">
      {!state.atTop && (
        <button className="up" type="button" onClick={() => go(-1)} title="Up a page" aria-label="Up a page">
          <Icon id="back" />
        </button>
      )}
      {!state.atEnd && (
        <button className="down" type="button" onClick={() => go(1)} title="Down a page" aria-label="Down a page">
          <Icon id="back" />
        </button>
      )}
    </div>
  );
}
