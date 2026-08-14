import { useRef, useState } from "react";
import { Icon } from "./Icons.jsx";

/** "I want to play something, I don't know what."
 *
 *  A shelf you have finished choosing from is a shelf you stop opening. This
 *  picks one thing and drops its title in the search box, which is where the
 *  answer would have gone if you had thought of it yourself — the list narrows
 *  to it, and clearing the box puts everything back.
 *
 *  Two details it would be easy to get wrong:
 *
 *  The roll ignores whatever is typed in the search box, but keeps every other
 *  filter. Keeping the search would be a trap: the first roll fills the box,
 *  which narrows the list to one item, and every roll after that would return
 *  that same item forever. Keeping the rest is the useful half — filter to the
 *  Xbox and it rolls an Xbox game.
 *
 *  It asks the server for a count and then for one row at a random offset,
 *  rather than picking from what is on screen. The list is paged, so picking
 *  locally would only ever choose from the first hundred — the newest hundred,
 *  which are the ones you least need reminding of.
 */
export function ShuffleButton({ fetcher, params, onPick, noun = "something" }) {
  const [busy, setBusy] = useState(false);
  const [empty, setEmpty] = useState(false);
  const last = useRef(null);

  const roll = async () => {
    setBusy(true);
    setEmpty(false);
    try {
      const { total } = await fetcher({ ...params, limit: 1 });
      if (!total) return setEmpty(true);

      let pick = null;
      // Twice at most: a die that lands on what it just landed on reads as
      // broken, but chasing a different answer through a two-item shelf would
      // never finish.
      for (let i = 0; i < 2; i++) {
        const at = Math.floor(Math.random() * total);
        const page = await fetcher({ ...params, limit: 1, offset: at });
        pick = page.items[0];
        if (!pick || total < 3 || pick.title !== last.current) break;
      }
      if (pick) {
        last.current = pick.title;
        onPick(pick.title);
      }
    } catch {
      // A roll that fails is not worth an error banner — the shelf is still
      // there and the button is still there. Nothing happened.
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      className={`dice ${busy ? "rolling" : ""}`}
      onClick={roll}
      disabled={busy}
      title={empty ? "Nothing here to pick from" : `Pick ${noun} at random`}
      aria-label={`Pick ${noun} at random`}
    >
      <Icon id="dice" />
    </button>
  );
}
