import { useRef, useState } from "react";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

// Photograph a card (phone camera) or pick a file — uploads to the API's
// bind-mounted image dir and hands back the stored /images/... URL.
export default function ImagePicker({ value, onChange, label = "Photo" }) {
  const [busy, setBusy] = useState(false);
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

  return (
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
        {busy ? "Uploading…" : value ? `Replace ${label.toLowerCase()}` : label}
      </button>
      {value && (
        <button type="button" className="ghost icon danger" title="Remove photo"
          onClick={() => onChange(null)}>
          <Icon id="x" />
        </button>
      )}
    </div>
  );
}
