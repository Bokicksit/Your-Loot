// Helpers for turning UPC-database product titles ("Akira Limited Edition
// Steelbook (4K Ultra HD + Blu-ray + Digital)") into search queries + fields.

export function detectFormat(title) {
  const t = title.toLowerCase();
  if (/4k|ultra\s*hd|\buhd\b/.test(t)) return "4K UHD";
  if (/blu-?ray|\bbd\b/.test(t)) return "Blu-ray";
  if (/\bdvd\b/.test(t)) return "DVD";
  if (/\bvhs\b/.test(t)) return "VHS";
  return null;
}

export function detectEdition(title) {
  const t = title.toLowerCase();
  if (t.includes("steelbook")) return "Steelbook";
  if (t.includes("criterion")) return "Criterion Collection";
  if (/collector'?s edition/.test(t)) return "Collector's Edition";
  if (/limited edition/.test(t)) return "Limited Edition";
  if (/director'?s cut/.test(t)) return "Director's Cut";
  return null;
}

// Product titles name the platform mid-string with junk after it
// ("Mega Man Legacy Collection 2 for PlayStation 4 Capcom"), so everything
// from the first platform mention onward is noise — cut there. The platform
// must be preceded by a separator/space, so titles that *start* with one
// ("Wii Sports", "PlayStation All-Stars") are never touched.
const PLATFORM_CUT =
  /[\s\-–—:,/]+(for\s+(the\s+)?)?((microsoft\s+)?xbox(\s*(360|one|series\s*[xs]))?|(sony\s+)?playstation(\s*[1-5]|\s+(portable|vita))?|ps[1-5]|psp|ps\s*vita|(super\s+)?nintendo(\s+(entertainment\s+system|switch|64|ds|3ds|gamecube|wii\s*u?))?|snes|nes|n64|gamecube|game\s*cube|wii\s*u?|game\s*boy(\s+(color|advance))?|gba|gbc|nds|3ds|sega(\s+(genesis|dreamcast|saturn|cd))?|genesis|dreamcast|pc)\b/i;

export function cleanGameTitle(title) {
  const t = cleanTitle(title);
  const m = t.match(PLATFORM_CUT);
  const cut = m ? t.slice(0, m.index) : t;
  return cut.replace(/[\s\-–—:,]+$/g, "").trim();
}

// Strip bracketed segments and format/edition noise so the remaining string
// works as a TMDB/IGDB query.
export function cleanTitle(title) {
  return title
    .replace(/\[[^\]]*\]|\([^)]*\)/g, " ")
    .replace(/4k(\s*(ultra\s*hd|uhd))?|ultra\s*hd|\buhd\b|blu-?ray|\bdvd\b|\bvhs\b|\bdigital\b/gi, " ")
    .replace(/steelbook|criterion( collection)?|collector'?s edition|limited edition|special edition|anniversary edition|director'?s cut/gi, " ")
    .replace(/[+/|]/g, " ")
    .replace(/\s{2,}/g, " ")
    .replace(/[\s\-–—:,]+$/g, "")
    .trim();
}
