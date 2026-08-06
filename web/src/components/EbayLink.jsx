import { ebayUrl } from "../ebay.js";
import { Icon } from "./Icons.jsx";

// The coin from the wanted list, on everything you already own too — what a
// copy is worth is the same question whether you're still hunting it or not.
export default function EbayLink({ title, terms, className = "ghost icon expand-ebay" }) {
  return (
    <a
      className={className}
      href={ebayUrl({ title, terms })}
      target="_blank"
      rel="noopener noreferrer"
      title="Check sold prices on eBay"
      onClick={(e) => e.stopPropagation()}
    >
      <Icon id="coin" />
    </a>
  );
}
