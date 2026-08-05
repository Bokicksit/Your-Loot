import { useRef, useState } from "react";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

// Mirrors MAX_BYTES in api/app/routers/images.py. Checked here too so an
// oversized photo fails at once instead of after pushing 20 MB over the wire —
// the server still enforces it, this is only about the wait.
const MAX_MB = 15;

// Give a card a picture two ways: photograph it (phone camera) or paste an
// image link (e.g. right-click → copy image address on pokemon.com). Pasted
// links are copied to the NAS so they keep working if the source moves.
export default function ImagePicker({ value, onChange, label = "Photo" }) {
  const [busy, setBusy] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [link, setLink] = useState("");
  const inputRef = useRef(null);

  const upload = async (file) => {
    if (!file) return;
    if (file.size > MAX_MB * 1024 * 1024) {
      alert(
        `That photo is ${(file.size / 1024 / 1024).toFixed(1)} MB — the limit is ` +
          `${MAX_MB} MB.\n\nShrink it, or use your phone's camera setting for a ` +
          `smaller picture.`
      );
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setBusy(true);
    try {
      const { url } = await api.uploadImage(file);
      onChange(url);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const grabLink = async () => {
    if (!link.trim() || busy) return;
    setBusy(true);
    try {
      const { url } = await api.fetchImage(link.trim());
      onChange(url);
      setLink("");
      setLinkOpen(false);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="img-picker">
      <div className="img-picker-row">
        {value ? (
          <img className="img-thumb" src={value} alt="" />
        ) : (
          <span className="img-thumb empty">
            <Icon id="card" />
          </span>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          capture="environment"
          style={{ display: "none" }}
          onChange={(e) => upload(e.target.files?.[0])}
        />
        <button
          type="button"
          className="ghost"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? "Working…" : value ? `Replace ${label.toLowerCase()}` : label}
        </button>
        <button
          type="button"
          className="ghost icon"
          title="Paste an image link"
          onClick={() => setLinkOpen(!linkOpen)}
        >
          <Icon id="link" />
        </button>
        {value && (
          <button
            type="button"
            className="ghost icon danger"
            title="Remove image"
            onClick={() => onChange(null)}
          >
            <Icon id="x" />
          </button>
        )}
      </div>
      {linkOpen && (
        <div className="form-row">
          <input
            type="text"
            className="grow"
            placeholder="Paste image address (https://…png)"
            value={link}
            onChange={(e) => setLink(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                grabLink();
              }
            }}
          />
          <button type="button" className="primary icon" onClick={grabLink} disabled={busy}>
            <Icon id="check" />
          </button>
        </div>
      )}
    </div>
  );
}
