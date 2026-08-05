// SVG sprite from the design project ("Get Loot UI Theme") + two app
// additions (trash, minus) drawn in the same 1.75-stroke style.
// Mount <IconDefs/> once in App; use <Icon id="star"/> anywhere.

export function IconDefs() {
  return (
    <svg width="0" height="0" style={{ position: "absolute", pointerEvents: "none" }} aria-hidden="true">
      <defs>
        <symbol id="i-card" viewBox="0 0 24 24"><rect x="5" y="3" width="14" height="18" rx="2.5" /><path d="M9 7.5h6M9 11h4" /></symbol>
        <symbol id="i-ball" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h5M15.5 12h5" /><circle cx="12" cy="12" r="2.8" /></symbol>
        <symbol id="i-star" viewBox="0 0 24 24"><path d="M12 3.6l2.72 5.62 6.18.86-4.47 4.31 1.08 6.11L12 17.6l-5.51 2.9 1.08-6.11L3.1 10.08l6.18-.86z" /></symbol>
        <symbol id="i-pad" viewBox="0 0 24 24"><rect x="2.5" y="7" width="19" height="11" rx="4.5" /><path d="M8 10.8v3.4M6.3 12.5h3.4" /><circle cx="15.8" cy="11.6" r="1.15" /><circle cx="18.4" cy="14.2" r="1.15" /></symbol>
        <symbol id="i-book" viewBox="0 0 24 24"><path d="M4 4.5h5.5A2.5 2.5 0 0112 7v12a2 2 0 00-2-2H4z" /><path d="M20 4.5h-5.5A2.5 2.5 0 0012 7v12a2 2 0 012-2h6z" /></symbol>
        <symbol id="i-console" viewBox="0 0 24 24"><rect x="3.5" y="8.5" width="17" height="8" rx="1.8" /><path d="M6.5 12.5h5M15.5 6v2.5M15.5 6h4M6 19v1.2M18 19v1.2" /><circle cx="17.2" cy="12.5" r="1" /></symbol>
        <symbol id="i-disc" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="2.4" /></symbol>
        <symbol id="i-vinyl" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.2" /><circle cx="12" cy="12" r="1" /></symbol>
        <symbol id="i-coin" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="5" /></symbol>
        <symbol id="i-sliders" viewBox="0 0 24 24"><path d="M4.5 7h15M4.5 12h9.5M4.5 17h5.5" /><circle cx="17" cy="12" r="2" /><circle cx="13.5" cy="17" r="2" /></symbol>
        <symbol id="i-x" viewBox="0 0 24 24"><path d="M6.5 6.5l11 11M17.5 6.5l-11 11" /></symbol>
        <symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5.5v13M5.5 12h13" /></symbol>
        <symbol id="i-minus" viewBox="0 0 24 24"><path d="M5.5 12h13" /></symbol>
        <symbol id="i-check" viewBox="0 0 24 24"><path d="M4.5 12.5l5 5 10-11" /></symbol>
        <symbol id="i-pencil" viewBox="0 0 24 24"><path d="M4.5 19.5l1.1-4.2L16.4 4.5a2 2 0 012.9 0l.2.2a2 2 0 010 2.9L8.7 18.4 4.5 19.5z" /><path d="M14.2 6.7l3.1 3.1" /></symbol>
        <symbol id="i-trash" viewBox="0 0 24 24"><path d="M4.5 6.5h15M9.5 6V4.5a1 1 0 011-1h3a1 1 0 011 1V6M7 6.5l.8 12a2 2 0 002 1.9h4.4a2 2 0 002-1.9l.8-12M10 10.5v5M14 10.5v5" /></symbol>
        <symbol id="i-link" viewBox="0 0 24 24"><path d="M10 14a3.6 3.6 0 010-5l2.5-2.5a3.6 3.6 0 015 5L16 13" /><path d="M14 10a3.6 3.6 0 010 5L11.5 17.5a3.6 3.6 0 01-5-5L8 11" /></symbol>
        <symbol id="i-alert" viewBox="0 0 24 24"><path d="M12 4.5l8.5 15h-17z" /><path d="M12 10v4M12 16.6v.1" /></symbol>
        <symbol id="i-scan" viewBox="0 0 24 24"><path d="M4 8.5V6a2 2 0 012-2h2.5M20 8.5V6a2 2 0 00-2-2h-2.5M4 15.5V18a2 2 0 002 2h2.5M20 15.5V18a2 2 0 01-2 2h-2.5M4 12h16" /></symbol>
        <symbol id="i-save" viewBox="0 0 24 24"><path d="M12 4v10.5M7.5 10.5l4.5 4.5 4.5-4.5" /><path d="M4.5 17v1.5a2 2 0 002 2h11a2 2 0 002-2V17" /></symbol>
        <symbol id="i-upload" viewBox="0 0 24 24"><path d="M12 20V9.5M7.5 13.5L12 9l4.5 4.5" /><path d="M4.5 7V5.5a2 2 0 012-2h11a2 2 0 012 2V7" /></symbol>
      </defs>
    </svg>
  );
}

export function Icon({ id }) {
  return (
    <svg className="i">
      <use href={`#i-${id}`} />
    </svg>
  );
}
