import { useRef, useState } from "react";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

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
