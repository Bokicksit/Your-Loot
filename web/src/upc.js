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
