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

// Publisher names, shared by the suffix stripper (safe, always applied) and
// the prefix stripper (risky — real titles start with publishers, so it's
// only used as a search *fallback*, never upfront).
const PUBLISHERS =
  "rockstar(\\s+games)?|capcom|nintendo(\\s+of\\s+america)?|electronic\\s+arts|ea(\\s+(games|sports))?|ubisoft|activision(\\s+blizzard)?|blizzard(\\s+entertainment)?|sony(\\s+(interactive|computer)\\s+entertainment)?|microsoft(\\s+(game\\s+)?studios)?|sega(\\s+of\\s+america)?|square\\s*(enix|soft)?|enix|konami|bandai(\\s+namco)?(\\s+(games|entertainment))?|namco|thq(\\s+nordic)?|atlus|bethesda(\\s+softworks)?|2k(\\s+(games|sports))?|take[-\\s]?two(\\s+interactive)?|warner\\s+bros\\.?(\\s+(games|interactive(\\s+entertainment)?))?|wb\\s+games|midway(\\s+games)?|atari|lucasarts|eidos(\\s+interactive)?|infogrames|acclaim(\\s+entertainment)?|vivendi(\\s+games)?|sierra(\\s+entertainment)?|hudson(\\s+soft)?|(tecmo\\s+)?koei(\\s+tecmo)?|tecmo|snk|nis\\s+america|xseed(\\s+games)?|natsume|working\\s+designs";

const PUBLISHER_SUFFIX = new RegExp(
  `[\\s\\-–—:,/]+(by\\s+)?(${PUBLISHERS})\\s*$`,
  "i"
);
const PUBLISHER_PREFIX = new RegExp(`^\\s*(${PUBLISHERS})[\\s\\-–—:,/]+`, "i");

// Fallback only: "Electronic Arts Mass Effect 2" -> "Mass Effect 2".
// Callers should try the unstripped title first — see GamesPage.onBarcode.
export function stripPublisherPrefix(title) {
  return title.replace(PUBLISHER_PREFIX, "").trim();
}

export function cleanGameTitle(title) {
  const t = cleanTitle(title);
  const m = t.match(PLATFORM_CUT);
  let cut = m ? t.slice(0, m.index) : t;
  let prev;
  do {
    prev = cut;
    cut = cut.replace(PUBLISHER_SUFFIX, "").trim();
  } while (cut !== prev);
  return cut.replace(/[\s\-–—:,]+$/g, "").trim();
}

// Comic publishers, which share nothing with the games list above. The
// house-name suffix is optional and matched separately, so "Marvel", "Marvel
// Comics" and "IDW Publishing" all come off without needing an entry each —
// and without the alternation being able to match "Marvel" out of "Marvel
// Comics" and leave "Comics" behind.
const COMIC_PUBLISHERS =
  "marvel|dc|image|dark\\s*horse|idw|boom!?|dynamite|valiant|vertigo|archie|titan|oni|fantagraphics|wildstorm|malibu|aftershock|vault|black\\s*mask";
const COMIC_PREFIX = new RegExp(
  `^\\s*(${COMIC_PUBLISHERS})(\\s+(comics?|publishing|entertainment|studios?|press|books))?[\\s\\-–—:,/]+`,
  "i"
);

// A retail listing for a single issue reads like "Marvel Comics Amazing
// Spider-Man #300 VF/NM" or "Saga Vol 1 #7 (Image)". Comic Vine wants the
// series and the issue number and nothing else, so pull those two out.
// Returns null when there's no issue number to find, which is the honest
// answer for a barcode that turned out to be a boxed set or a magazine.
// A comic's main barcode identifies the *title*, not the issue — the issue
// lives in the separate five-digit add-on printed beside it ("00111" = issue
// 001, cover 1, first printing). So the issue number here is only ever a guess
// read out of the shop's product title, and it is better to return none than
// to invent one.
// Shop listings for comics come out as delimited fields whose delimiter has
// usually been mangled into "?" somewhere along the way:
//   "Comic Book?Guardians of The Galaxy?Issue 7?Marvel: Nov 26, 2008?Sleeved"
const FIELD_SEP = /[?|•·¦•�]+/g;
// fields that describe the listing rather than the comic
const NOISE =
  /^(comic books?|comics?|sleeved|bagged( and boarded)?|boarded|new|used|key issue|direct edition|newsstand|(near )?mint|nm(\/m)?|vf(\/nm)?|fn|vg|raw|ungraded)$/i;
// a whole field that is nothing but the issue number
const ISSUE_FIELD = /^(?:issue|iss\.?|no\.?|number|#)\s*#?\s*(\d+)\s*$/i;
// a field that is the publisher and a date, not a title
const PUBLISHER_DATE = /^[^:]{2,24}:\s*\w/;

export function comicQuery(title) {
  const cleaned = String(title || "")
    .replace(/\[[^\]]*\]|\([^)]*\)/g, " ")
    .replace(FIELD_SEP, " | ");
  const parts = cleaned
    .split("|")
    .map((s) => s.replace(/\s{2,}/g, " ").trim())
    .filter(Boolean)
    .filter((p) => !NOISE.test(p));
  if (!parts.length) return null;

  // Structured listing: an "Issue 7" field of its own, with the title in the
  // field before it. This is the common shape and the only one that gives an
  // issue number worth trusting.
  for (let i = 1; i < parts.length; i++) {
    const m = parts[i].match(ISSUE_FIELD);
    if (m) {
      const series = tidySeries(parts[i - 1]);
      if (series) return { series, issue: m[1], coverYear: coverYear(cleaned) };
    }
  }

  // Otherwise work inside the most title-like field.
  const head = parts.find((p) => !PUBLISHER_DATE.test(p) && !ISSUE_FIELD.test(p)) || parts[0];
  // "Vol 1" is the run, not the issue, so it goes before anything looks for a
  // bare number — otherwise half the scans come back as issue 1
  const noVol = head.replace(/\bvol(ume)?\.?\s*\d+\b/gi, " ");
  // A number after a # or the word "issue" is an issue and nothing else. A
  // bare trailing number is a guess, and one that reads like a year is almost
  // always the year — no comic has reached issue 1900, and the longest-running
  // title is only in the 1000s, so the range is free to reject.
  let m = noVol.match(/(?:#|\bissue\s*#?)\s*(\d+)/i);
  if (!m) {
    const bare = noVol.match(/\s(\d{1,4})\b(?!.*\d)/);
    if (bare && !(Number(bare[1]) >= 1900 && Number(bare[1]) <= 2099)) m = bare;
  }
  // No issue number to be had: still worth handing back the series, because
  // searching the run and picking the issue beats being told nothing was found.
  const series = tidySeries(m ? noVol.slice(0, m.index) : noVol);
  if (!series) return null;
  return { series, issue: m ? m[1] : null, coverYear: coverYear(cleaned) };
}

// The listing usually carries the on-sale date ("Marvel: Nov 26, 2008"). That
// is the cover year, not the year the run started — an issue from deep in a
// long run has a cover year nothing like its volume year — so it fills the
// cover year box and nothing else.
function coverYear(text) {
  const years = [...String(text).matchAll(/\b(19\d{2}|20\d{2})\b/g)].map((m) => Number(m[1]));
  return years.length ? String(Math.max(...years)) : null;
}

function tidySeries(raw) {
  let series = String(raw || "")
    // a year hanging off the end is the run's date, not part of its name, and
    // leaving it on stops Comic Vine matching the series at all
    .replace(/[\s(,-]+(19\d{2}|20\d{2})\s*$/, "")
    .replace(/[\s\-–—:,#]+$/g, "")
    .trim();
  // "Marvel Comics Amazing Spider-Man" -> "Amazing Spider-Man". Never strip
  // all the way to nothing, though: Archie and Vertigo put out series named
  // after themselves, and there the publisher is the whole title.
  const trimmed = series.replace(COMIC_PREFIX, "").trim();
  if (trimmed) series = trimmed;
  return series;
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
