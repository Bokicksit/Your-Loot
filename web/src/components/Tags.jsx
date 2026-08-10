import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

/* Your own words for your own things.
 *
 * A tag is made by typing it — there is no list to create first — so the
 * editor is one text box that happens to remember what you have used before.
 * The suggestions are a native <datalist>: it opens on focus, filters as you
 * type, and behaves like the keyboard's own autocomplete on a phone, which no
 * hand-rolled dropdown manages for free.
 *
 * Scope is the collection as the app shows it. Hardware asks for its own
 * words rather than inheriting games'.
 */

/** Read-only chips. Lives in an opened detail panel and nowhere else — a tile
 *  is a picture of the thing, and a row is one line, so neither has room for
 *  labels that only matter once you've opened it. */
export function TagChips({ tags }) {
  if (!tags?.length) return null;
  return (
    <div className="tag-chips">
      {tags.map((t) => (
        <span key={t} className="chip tag">
          {t}
        </span>
      ))}
    </div>
  );
}

/** The filter control, shaped like the other facet selects so it sits in the
 *  same row without announcing itself. Tags nobody is using are left out —
 *  they still exist, and still autocomplete, but an empty chip is noise. */
export function TagFilter({ scope, value, onChange, reloadKey, includeWanted }) {
  const [tags, setTags] = useState([]);

  useEffect(() => {
    let alive = true;
    api
      .tags(scope, includeWanted ? { include_wanted: true } : {})
      .then((r) => alive && setTags(r.tags.filter((t) => t.count > 0)))
      .catch(() => alive && setTags([]));
    return () => {
      alive = false;
    };
  }, [scope, reloadKey, includeWanted]);

  // Keep it mounted while a filter is active even if the count went to zero,
  // or clearing the filter becomes impossible: the control that set it is
  // gone and the list stays mysteriously empty.
  if (!tags.length && !value) return null;

  return (
    <select
      className="chip-select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">All tags</option>
      {tags.map((t) => (
        <option key={t.id} value={t.value}>
          {t.value} ({t.count})
        </option>
      ))}
      {value && !tags.some((t) => t.value === value) && (
        <option value={value}>{value} (0)</option>
      )}
    </select>
  );
}

/** The editor: current tags as removable chips, plus a box to add another.
 *  `value` is a list of names and `onChange` gets the new list — it holds no
 *  state of its own, so the same control works on a form for an item that
 *  doesn't exist yet and on one that does. */
export function TagEditor({ scope, value = [], onChange, id }) {
  const [draft, setDraft] = useState("");
  const [known, setKnown] = useState([]);
  const listId = `tags-${scope}-${id || "new"}`;

  useEffect(() => {
    let alive = true;
    api
      .tags(scope)
      .then((r) => alive && setKnown(r.tags.map((t) => t.value)))
      .catch(() => alive && setKnown([]));
    return () => {
      alive = false;
    };
  }, [scope]);

  // Same folding the server does, so a near-miss is caught before it is sent
  // rather than coming back as a surprise rename.
  const fold = (s) => s.replace(/[-_]/g, " ").trim().replace(/\s+/g, " ").toLowerCase();

  function add(raw) {
    const name = raw.trim().replace(/\s+/g, " ").slice(0, 40);
    if (!name) return;
    const key = fold(name);
    if (value.some((t) => fold(t) === key)) return setDraft("");
    // prefer the spelling already in use over the one just typed
    const existing = known.find((t) => fold(t) === key);
    onChange([...value, existing || name]);
    setDraft("");
  }

  function onKeyDown(e) {
    if (e.key === "Enter" || e.key === ",") {
      // Enter in a tag box means "add this tag", never "submit the form" —
      // otherwise typing one and reaching for the next saves the record.
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="tag-editor">
      {value.map((t) => (
        <span key={t} className="chip tag">
          {t}
          <button
            type="button"
            title={`Remove ${t}`}
            onClick={() => onChange(value.filter((x) => x !== t))}
          >
            <Icon id="x" />
          </button>
        </span>
      ))}
      <input
        type="text"
        list={listId}
        className="tag-input"
        placeholder={value.length ? "Add another…" : "Tags — hip-hop, want to play…"}
        value={draft}
        maxLength={40}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        // committing on blur means a typed-but-unentered tag isn't silently
        // dropped when you go straight from the box to Save
        onBlur={() => add(draft)}
      />
      <datalist id={listId}>
        {known
          .filter((t) => !value.some((v) => fold(v) === fold(t)))
          .map((t) => (
            <option key={t} value={t} />
          ))}
      </datalist>
    </div>
  );
}
