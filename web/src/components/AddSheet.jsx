import { createPortal } from "react-dom";
import { Icon } from "./Icons.jsx";
import HelpTip from "./HelpTip.jsx";

// The shell both halves of adding an item share.
//
// Searching and describing used to happen in one long form, where the top box
// looked for a title online and the boxes under it described the copy in your
// hand — two different jobs wearing the same clothes. They're two steps now,
// and only one is ever on screen.
//
// Rendered through a portal: the page's add button lives inside the toolbar,
// and a modal nested in there inherits its layout.
// `help` is a short note on how this step works, behind a "?" in the header —
// written per collection, because "how do I find a comic" and "how do I find
// a record" have genuinely different answers.
export default function AddSheet({ open, title, onClose, onBack, help, children }) {
  if (!open) return null;
  return createPortal(
    <div className="modal-scrim" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          {onBack && (
            <button type="button" className="ghost icon" title="Back to search" onClick={onBack}>
              <Icon id="back" />
            </button>
          )}
          <h2>{title}</h2>
          {help && <HelpTip label="How this works">{help}</HelpTip>}
          <button
            type="button"
            className="ghost icon"
            title="Close"
            onClick={onClose}
            style={{ marginLeft: "auto" }}
          >
            <Icon id="x" />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  );
}

// Shown where the results are about to appear, for as long as the lookup
// takes. Some of these searches are genuinely slow — a comic run can be five
// requests deep — and a button that quietly changes to "…" reads as nothing
// happening at all.
export function Searching({ what = "Searching" }) {
  return (
    <p className="searching" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {what}…
    </p>
  );
}

// The line at the bottom of the search step: the way through to typing it in
// yourself, for everything the databases have never heard of.
export function ByHand({ onClick, children = "Enter it by hand" }) {
  return (
    <button type="button" className="ghost by-hand" onClick={onClick}>
      {children}
      <Icon id="pencil" />
    </button>
  );
}
