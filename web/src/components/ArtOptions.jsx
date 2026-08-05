// Artwork candidates for an item being added: retailer photos of the actual
// case (from the barcode) alongside the poster/cover art from the metadata
// source. Shown together because for a physical collection the box you own is
// usually the better picture, but not always — the sharpest one wins, and
// that's a judgement only the person holding it can make.
export default function ArtOptions({ options, value, onChange }) {
  if (!options.length) return null;
  return (
    <div className="art-options">
      <span className="art-label">
        Artwork — pick the one that matches your copy
      </span>
      <div className="art-strip">
        {options.map((o) => (
          <button
            type="button"
            key={o.url}
            className={`art-thumb ${value === o.url ? "on" : ""}`}
            onClick={() => onChange(o.url)}
            title={o.kind === "box" ? "Photo of the case" : "Poster / cover art"}
          >
            <img src={o.url} alt="" loading="lazy" />
            <small>{o.kind === "box" ? "case" : "poster"}</small>
          </button>
        ))}
      </div>
    </div>
  );
}
