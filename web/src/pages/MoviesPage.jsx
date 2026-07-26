import { Icon } from "../components/Icons.jsx";

// Placeholder — phase 2 wires this to /api/movies + TMDB metadata lookup.
export default function MoviesPage() {
  return (
    <div className="empty" style={{ marginTop: "16px" }}>
      <span className="glyph"><Icon id="disc" /></span>
      <strong>Shelf is empty</strong>
      <p>
        Movies arrive in phase 2: TMDB metadata plus your format, edition, and
        region-code details. The schema is already waiting.
      </p>
    </div>
  );
}
