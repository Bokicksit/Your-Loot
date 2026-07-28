// The symbol printed on the card: ● common, ◆ uncommon, ★ rare — black for
// standard, silver-ish for ultra, gold for IR/SIR/hyper. Tooltip = full text.
export default function RarityMark({ rarity }) {
  if (!rarity) return null;
  const r = rarity.toLowerCase();
  let sym = null;
  let cls = "mark-bw";
  if (r === "common") sym = "●";
  else if (r === "uncommon") sym = "◆";
  else if (r.includes("special illustration")) [sym, cls] = ["★★", "mark-gold"];
  else if (r.includes("illustration")) [sym, cls] = ["★", "mark-gold"];
  else if (r.includes("hyper")) [sym, cls] = ["★★★", "mark-gold"];
  else if (r.includes("secret") || r.includes("rainbow")) [sym, cls] = ["★★", "mark-gold"];
  else if (r.includes("ultra")) [sym, cls] = ["★★", "mark-silver"];
  else if (r.includes("double")) sym = "★★";
  else if (r.includes("rare")) sym = "★";
  else if (r.includes("promo")) sym = "P";
  if (!sym) return null;
  return (
    <span className={`rarity-mark ${cls}`} title={rarity}>
      {sym}
    </span>
  );
}
