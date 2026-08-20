// SVG sprite for the whole app — one 1.75-stroke style throughout.
// Mount <IconDefs/> once in App; use <Icon id="star"/> anywhere.

export function IconDefs() {
  return (
    <svg width="0" height="0" style={{ position: "absolute", pointerEvents: "none" }} aria-hidden="true">
      <defs>
        <symbol id="i-card" viewBox="0 0 24 24"><rect x="3.6" y="6" width="9" height="13" rx="2" transform="rotate(-13 8.1 12.5)"></rect> <rect x="10" y="4" width="10.5" height="16" rx="2" fill="var(--bg-1)"></rect> <circle cx="15.25" cy="12" r="2.6"></circle> <path d="M10 12h2.65M17.85 12h2.65"></path></symbol>
        <symbol id="i-ball" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h5M15.5 12h5" /><circle cx="12" cy="12" r="2.8" /></symbol>
        <symbol id="i-star" viewBox="0 0 24 24"><path d="M12 3.6l2.72 5.62 6.18.86-4.47 4.31 1.08 6.11L12 17.6l-5.51 2.9 1.08-6.11L3.1 10.08l6.18-.86z" /></symbol>
        <symbol id="i-pad" viewBox="0 0 24 24"><path d="M7.6 7.5h8.8a4.6 4.6 0 0 1 4.5 3.7l.75 4.3a2.5 2.5 0 0 1-4.65 1.7L15.6 14.8H8.4l-1.4 2.4a2.5 2.5 0 0 1-4.65-1.7l.75-4.3A4.6 4.6 0 0 1 7.6 7.5z"></path> <path d="M6.1 11.4h2.9M7.55 9.95v2.9"></path> <circle cx="15.4" cy="10.6" r=".95" fill="currentColor" stroke="none"></circle> <circle cx="17.7" cy="12.4" r=".95" fill="currentColor" stroke="none"></circle></symbol>
        <symbol id="i-book" viewBox="0 0 24 24"><rect x="3.4" y="4" width="4.6" height="16" rx="1.3"></rect> <rect x="9.2" y="4" width="4.6" height="16" rx="1.3"></rect> <rect x="15.2" y="5.6" width="4.6" height="14.4" rx="1.3" transform="rotate(11 17.5 12.8)"></rect> <path d="M5.7 8.2v-1.4M11.5 8.2v-1.4"></path></symbol>
        <symbol id="i-console" viewBox="0 0 24 24"><rect x="2.6" y="8.4" width="13.4" height="10.2" rx="2.2"></rect> <path d="M5.6 11.6h5.4M5.6 14.6h2.4"></path> <circle cx="13.2" cy="15" r="1.05" fill="currentColor" stroke="none"></circle> <path d="M16 11.4h2.6a2.6 2.6 0 0 0 2.6-2.6V7.2"></path> <rect x="16.4" y="4.2" width="4.4" height="3" rx="1"></rect></symbol>
        <symbol id="i-disc" viewBox="0 0 24 24"><rect x="3" y="9.6" width="18" height="10.4" rx="2.2"></rect> <path d="M3.5 9.6 3.9 6.2a1 1 0 0 1 1.12-.87l15 1.75a1 1 0 0 1 .87 1.12l-.15 1.4"></path> <path d="M8.4 5.7 6.7 9.4M13.4 6.3 11.7 9.9M18.4 6.9 16.7 10.4"></path></symbol>
        <symbol id="i-vinyl" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.4"></circle> <circle cx="12" cy="12" r="4.4"></circle> <circle cx="12" cy="12" r="1.15" fill="currentColor" stroke="none"></circle></symbol>
        <symbol id="i-coin" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.6"></circle> <circle cx="12" cy="12" r="6.2"></circle> <path d="M14.1 9.5a2.1 2.1 0 00-2-1.2h-.4a1.9 1.9 0 00-.3 3.75l1.6.3a1.9 1.9 0 01-.3 3.75h-.4a2.1 2.1 0 01-2-1.2M12 7v1.3M12 15.7V17"></path></symbol>
        <symbol id="i-sliders" viewBox="0 0 24 24"><path d="M4.5 7h15M4.5 12h9.5M4.5 17h5.5" /><circle cx="17" cy="12" r="2" /><circle cx="13.5" cy="17" r="2" /></symbol>
        {/* The settings accordion's glyphs, from the design system. One per
            section, so a head is recognisable before it is read. */}
        <symbol id="i-user" viewBox="0 0 24 24"><circle cx="12" cy="8.5" r="3.8" /><path d="M4.8 20a7.4 7.4 0 0114.4 0" /></symbol>
        <symbol id="i-globe" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.4 2.4 3.6 5.3 3.6 8.5S14.4 18.1 12 20.5c-2.4-2.4-3.6-5.3-3.6-8.5S9.6 5.9 12 3.5z" /></symbol>
        <symbol id="i-lock" viewBox="0 0 24 24"><rect x="4.5" y="10.5" width="15" height="9.5" rx="2.4" /><path d="M8 10.5V8a4 4 0 018 0v2.5" /><path d="M12 14.2v2.4" /></symbol>
        <symbol id="i-box" viewBox="0 0 24 24"><path d="M4 8.2l8-3.7 8 3.7v7.6l-8 3.7-8-3.7z" /><path d="M4 8.2l8 3.7 8-3.7M12 11.9V19.5" /></symbol>
        {/* points down when shut and is rotated when open — one glyph, two
            states, rather than two glyphs that can disagree */}
        <symbol id="i-chev" viewBox="0 0 24 24"><path d="M6.5 9.5L12 15l5.5-5.5" /></symbol>
        <symbol id="i-copy" viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2.2" /><path d="M15 6.5A2.5 2.5 0 0012.5 4h-6A2.5 2.5 0 004 6.5v6A2.5 2.5 0 006.5 15" /></symbol>
        <symbol id="i-down" viewBox="0 0 24 24"><path d="M12 4.5v11M7.5 11.5L12 16l4.5-4.5M5 19.5h14" /></symbol>
        <symbol id="i-up" viewBox="0 0 24 24"><path d="M12 16V5M7.5 9L12 4.5 16.5 9M5 19.5h14" /></symbol>
        {/* nine pockets to a page — the shape of a binder page, which is what
            it stands for */}
        <symbol id="i-grid" viewBox="0 0 24 24"><rect x="3.5" y="3.5" width="17" height="17" rx="2" /><path d="M9.17 3.5v17M14.83 3.5v17M3.5 9.17h17M3.5 14.83h17" /></symbol>
        <symbol id="i-x" viewBox="0 0 24 24"><path d="M6.5 6.5l11 11M17.5 6.5l-11 11" /></symbol>
        <symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5.5v13M5.5 12h13" /></symbol>
        <symbol id="i-minus" viewBox="0 0 24 24"><path d="M5.5 12h13" /></symbol>
        <symbol id="i-check" viewBox="0 0 24 24"><path d="M4.5 12.5l5 5 10-11" /></symbol>
        <symbol id="i-pencil" viewBox="0 0 24 24"><path d="M4.5 19.5l1.1-4.2L16.4 4.5a2 2 0 012.9 0l.2.2a2 2 0 010 2.9L8.7 18.4 4.5 19.5z" /><path d="M14.2 6.7l3.1 3.1" /></symbol>
        <symbol id="i-trash" viewBox="0 0 24 24"><path d="M4.5 6.5h15M9.5 6V4.5a1 1 0 011-1h3a1 1 0 011 1V6M7 6.5l.8 12a2 2 0 002 1.9h4.4a2 2 0 002-1.9l.8-12M10 10.5v5M14 10.5v5" /></symbol>
        <symbol id="i-fig" viewBox="0 0 24 24"><circle cx="12" cy="6.5" r="2.6" /><path d="M8.5 19v-3.5a3.5 3.5 0 017 0V19" /><path d="M5.5 20.5h13" /></symbol>
        <symbol id="i-term" viewBox="0 0 24 24"><rect x="3" y="4.5" width="18" height="15" rx="2.4" /><path d="M7 10l2.6 2.2L7 14.4M12 15h5" /></symbol>
        <symbol id="i-cloud" viewBox="0 0 24 24"><path d="M7.5 18h9.2a3.8 3.8 0 00.4-7.6A5.6 5.6 0 006.9 9.2 3.9 3.9 0 007.5 18z" /></symbol>
        <symbol id="i-heart" viewBox="0 0 24 24"><path d="M12 19.5s-7-4.3-7-9a3.9 3.9 0 017-2.4A3.9 3.9 0 0119 10.5c0 4.7-7 9-7 9z" /></symbol>
        <symbol id="i-link" viewBox="0 0 24 24"><path d="M10 14a3.6 3.6 0 010-5l2.5-2.5a3.6 3.6 0 015 5L16 13" /><path d="M14 10a3.6 3.6 0 010 5L11.5 17.5a3.6 3.6 0 01-5-5L8 11" /></symbol>
        <symbol id="i-alert" viewBox="0 0 24 24"><path d="M12 4.5l8.5 15h-17z" /><path d="M12 10v4M12 16.6v.1" /></symbol>
        <symbol id="i-info" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5.5M12 7.7v.1" /></symbol>
        <symbol id="i-help" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><path d="M9.5 9.3a2.6 2.6 0 115 .9c-.55.9-2.5 1.3-2.5 2.9M12 16.4v.1" /></symbol>
        <symbol id="i-camera" viewBox="0 0 24 24"><path d="M3.5 8.5h3l1.6-2.4h7.8l1.6 2.4h3v10a1.5 1.5 0 01-1.5 1.5H5a1.5 1.5 0 01-1.5-1.5z" /><circle cx="12" cy="13.4" r="3.4" /></symbol>
        <symbol id="i-target" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="3.4" /><path d="M12 1.8v3.4M12 18.8v3.4M1.8 12h3.4M18.8 12h3.4" /></symbol>
        {/* a magnifier, for looking something up by name — the scan
            frame next to it means point the camera at a barcode, and
            the two buttons sat side by side wearing the same glyph */}
        <symbol id="i-search" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5" /><path d="M15.4 15.4L20 20" /></symbol>
        <symbol id="i-scan" viewBox="0 0 24 24"><path d="M4 8.5V6a2 2 0 012-2h2.5M20 8.5V6a2 2 0 00-2-2h-2.5M4 15.5V18a2 2 0 002 2h2.5M20 15.5V18a2 2 0 01-2 2h-2.5M4 12h16" /></symbol>
        <symbol id="i-save" viewBox="0 0 24 24"><path d="M12 4v10.5M7.5 10.5l4.5 4.5 4.5-4.5" /><path d="M4.5 17v1.5a2 2 0 002 2h11a2 2 0 002-2V17" /></symbol>
        <symbol id="i-upload" viewBox="0 0 24 24"><path d="M12 20V9.5M7.5 13.5L12 9l4.5 4.5" /><path d="M4.5 7V5.5a2 2 0 012-2h11a2 2 0 012 2V7" /></symbol>
        <symbol id="i-brick" viewBox="0 0 24 24"><rect x="3.4" y="9.2" width="17.2" height="9.6" rx="1.8"></rect> <path d="M6.6 9.2V7.4a1.4 1.4 0 0 1 1.4-1.4h1.6a1.4 1.4 0 0 1 1.4 1.4v1.8M13 9.2V7.4A1.4 1.4 0 0 1 14.4 6H16a1.4 1.4 0 0 1 1.4 1.4v1.8"></path></symbol>
        <symbol id="i-back" viewBox="0 0 24 24"><path d="M19 12H5.5M11 5.5L4.5 12l6.5 6.5" /></symbol>
        <symbol id="i-bolt" viewBox="0 0 24 24"><path d="M13.2 3.5L5.5 13.4h5.4l-.9 7.1 7.7-9.9h-5.4z" /></symbol>
        <symbol id="i-comic" viewBox="0 0 24 24"><rect x="3.5" y="3.5" width="17" height="17" rx="2.4"></rect> <path d="M7.6 7.8h8.8v4.9h-4.9l-2.9 2.9v-2.9H7.6z"></path></symbol>
        <symbol id="i-tiles" viewBox="0 0 24 24"><rect x="4" y="4" width="7" height="7" rx="1.4" /><rect x="13" y="4" width="7" height="7" rx="1.4" /><rect x="4" y="13" width="7" height="7" rx="1.4" /><rect x="13" y="13" width="7" height="7" rx="1.4" /></symbol>
        {/* five pips rather than one or two: at this size a die needs enough
            of them to stop reading as a plain rounded square */}
        <symbol id="i-dice" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="3.4"></rect> <circle cx="8.5" cy="8.5" r="1.15" fill="currentColor" stroke="none"></circle> <circle cx="15.5" cy="8.5" r="1.15" fill="currentColor" stroke="none"></circle> <circle cx="12" cy="12" r="1.15" fill="currentColor" stroke="none"></circle> <circle cx="8.5" cy="15.5" r="1.15" fill="currentColor" stroke="none"></circle> <circle cx="15.5" cy="15.5" r="1.15" fill="currentColor" stroke="none"></circle></symbol>
        <symbol id="i-list" viewBox="0 0 24 24"><rect x="3.5" y="5" width="5" height="5" rx="1.2" /><rect x="3.5" y="14" width="5" height="5" rx="1.2" /><path d="M11.5 6.6h9M11.5 9.4h6M11.5 15.6h9M11.5 18.4h6" /></symbol>
      </defs>
    </svg>
  );
}

export function Icon({ id, className = "" }) {
  // `.i` always, plus whatever the caller needs to style this one — the
  // accordion's chevron rotates, and that has to be aimed at the glyph
  // rather than at a wrapper around it.
  return (
    <svg className={`i ${className}`.trim()}>
      <use href={`#i-${id}`} />
    </svg>
  );
}

/** The mark: a shelf holding a book, a record, a disc and a card.
 *
 *  Not in the sprite, and not an <Icon>. The sprite is one weight throughout
 *  and `.i` sets stroke-width in CSS, which beats the presentation attributes
 *  below — the mark draws in five weights across a 120 grid, so borrowing that
 *  class would flatten every one of them into the same hairline.
 *
 *  Inherits `currentColor`, so it takes the gold from whatever it sits in
 *  rather than carrying a hex around.
 */
export function BrandMark({ size = 22 }) {
  return (
    <svg
      className="mark"
      viewBox="0 0 120 120"
      width={size}
      height={size}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="ylCubeMark" x1="0" y1="0" x2="1" y2="0.7">
          <stop offset="0" stopColor="#8b46f0" />
          <stop offset="0.5" stopColor="#7c4dff" />
          <stop offset="1" stopColor="#3b82f6" />
        </linearGradient>
        {/* The icon files paint the seams in the brand background, which is
            right in a launcher and wrong here — the top bar is a lighter
            shade, so a painted seam would read as a dark line across the
            cube. Cutting them as transparency instead lets whatever is behind
            the mark show through, on either bar and at any size. */}
        <mask id="ylCubeMarkCut" maskUnits="userSpaceOnUse" x="0" y="0" width="120" height="120">
          <rect width="120" height="120" fill="#000" />
          <g strokeLinejoin="round" strokeLinecap="round">
            <path d="M60 12 L106 39 L60 66 L14 39 Z" fill="#fff" stroke="#fff" strokeWidth="7" />
            <path d="M14 39 L60 66 L60 110 L14 83 Z" fill="#fff" stroke="#fff" strokeWidth="7" />
            <path d="M106 39 L60 66 L60 110 L106 83 Z" fill="#fff" stroke="#fff" strokeWidth="7" />
            <path d="M14 39 L60 66 L106 39" fill="none" stroke="#000" strokeWidth="10" />
            <path d="M60 66 V110" fill="none" stroke="#000" strokeWidth="10" />
            <rect x="45" y="39" width="30" height="35" rx="8" fill="#000" stroke="#000" strokeWidth="10" />
            <path d="M55 48 V66 H68" fill="none" stroke="#fff" strokeWidth="7" />
          </g>
        </mask>
      </defs>
      <rect width="120" height="120" fill="url(#ylCubeMark)" mask="url(#ylCubeMarkCut)" />
    </svg>
  );
}
