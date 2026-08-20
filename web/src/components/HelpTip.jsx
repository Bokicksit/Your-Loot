import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "./Icons.jsx";

// A "?" that answers itself — tap it and a short note appears, tap anywhere
// else and it goes. For the places a first-timer hesitates: what a form is
// for, what its buttons do, what happens after.
//
// Deliberately not a hover tooltip: most of this app's use is on a phone,
// where hover does not exist. The note is a click away on every device, the
// same way.
export default function HelpTip({ label = "What's this?", children }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const popRef = useRef(null);

  // The note is anchored to the icon, but the icon can sit anywhere — hard
  // against either edge of a row. Measure once it's on screen and nudge it
  // sideways so it never leaves the viewport.
  useLayoutEffect(() => {
    if (!open || !popRef.current) return;
    const el = popRef.current;
    el.style.marginLeft = "0px";
    const r = el.getBoundingClientRect();
    const overRight = r.right - (window.innerWidth - 8);
    const overLeft = 8 - r.left;
    if (overRight > 0) el.style.marginLeft = `${-overRight}px`;
    else if (overLeft > 0) el.style.marginLeft = `${overLeft}px`;
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const away = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const key = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", key);
    };
  }, [open]);

  return (
    <span className="help-tip" ref={ref}>
      <button
        type="button"
        className={`ghost icon${open ? " on" : ""}`}
        title={label}
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Icon id="help" />
      </button>
      {open && (
        <span className="help-pop" role="note" ref={popRef}>
          {children}
        </span>
      )}
    </span>
  );
}
