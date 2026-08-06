// A sold-and-completed eBay search: the closest thing to a market price
// without paying for a pricing API.
//
// Nothing here is stored on the item. The link is assembled from whatever the
// entry says at the moment you open it, so every item you already own gets one
// with no migration and no re-adding, and it follows any edit you make.

// Only the sized pressings collapse: nobody lists a `2x12" Vinyl`, they write
// "vinyl". Everything else is already what a seller would type, and "Vinyl box
// set" has to keep its second half or the search drops to loose LPs.
function tidy(term) {
  const s = String(term ?? "").trim();
  if (!s) return null;
  return /^\d*x?\d+"\s*vinyl$/i.test(s) ? "vinyl" : s;
}

// `terms` are extra qualifiers in priority order — the platform, the pressing,
// the set number. Each caller picks its own, because what separates two
// listings differs per collection and the wrong qualifier is worse than none:
// a region code, say, is something almost no seller writes in a listing.
export function ebayUrl({ title, terms = [] }) {
  // strip our "(1995)" year suffix — it needlessly narrows eBay matches
  const name = String(title ?? "").replace(/\s*\(\d{4}\)\s*$/, "").trim();
  const q = [name].filter(Boolean);
  for (const raw of terms) {
    const term = tidy(raw);
    // saying it twice buys nothing and can cost matches
    if (term && !q.some((s) => s.toLowerCase().includes(term.toLowerCase()))) {
      q.push(term);
    }
  }
  const nkw = encodeURIComponent(q.join(" "));
  return `https://www.ebay.com/sch/i.html?_nkw=${nkw}&LH_Sold=1&LH_Complete=1`;
}
