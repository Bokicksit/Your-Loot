import { useRef, useState } from "react";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";
import GuidedCamera from "./GuidedCamera.jsx";
import PhotoCrop from "./PhotoCrop.jsx";

// Mirrors MAX_BYTES in api/app/routers/images.py. Checked here too so an
// oversized photo fails at once instead of after pushing 20 MB over the wire —
// the server still enforces it, this is only about the wait.
const MAX_MB = 15;

// Give a card a picture two ways: photograph it (phone camera) or paste an
// image link (e.g. right-click → copy image address on pokemon.com). Pasted
// links are copied to the NAS so they keep working if the source moves.
export default function ImagePicker({
  value,
  onChange,
  label = "Photo",
  // some pictures aren't the collector's to delete — a catalog card's art is
  // reference data, and blanking it just leaves a hole
  removable = true,
  removeHint,
  // sleeves are square; cards, books and cases are portrait
  square = false,
}) {
  const [busy, setBusy] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [link, setLink] = useState("");
  const inputRef = useRef(null);
  const cameraRef = useRef(null);
  const [guideOpen, setGuideOpen] = useState(false);
  // getUserMedia is refused outside a secure context, so on a plain-http LAN
  // this simply is not offered and the native camera still is.
  const canGuide =
    typeof window !== "undefined" &&
    window.isSecureContext &&
    !!navigator.mediaDevices?.getUserMedia;

  // The ✕ sits next to buttons that only add things, and it takes the picture
  // with one tap and no undo. Ask first.
  const removeImage = () => {
    const what = label.toLowerCase();
    if (!confirm(`Remove this ${what}?` + (removeHint ? `\n\n${removeHint}` : "")))
      return;
    onChange(null);
  };

  // Chosen but not sent yet — it goes through the cropper first.
  const [pending, setPending] = useState(null);

  const choose = (file, input) => {
    if (input) input.value = ""; // so the same file can be picked twice
    if (!file) return;
    if (file.size > MAX_MB * 1024 * 1024) {
      alert(
        `That photo is ${(file.size / 1024 / 1024).toFixed(1)} MB — the limit is ` +
          `${MAX_MB} MB.\n\nShrink it, or use your phone's camera setting for a ` +
          `smaller picture.`
      );
      return;
    }
    setPending(file);
  };

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
          <img className={`img-thumb ${square ? "square" : ""}`} src={value} alt="" />
        ) : (
          <span className={`img-thumb blank ${square ? "square" : ""}`}>
            <Icon id={square ? "vinyl" : "card"} />
          </span>
        )}
        {/* no `capture` here — that attribute sends phones straight to the
            camera and takes the photo library away entirely */}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          style={{ display: "none" }}
          onChange={(e) => choose(e.target.files?.[0], e.target)}
        />
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          style={{ display: "none" }}
          onChange={(e) => choose(e.target.files?.[0], e.target)}
        />
        <button
          type="button"
          className="ghost"
          disabled={busy}
          title={`Upload a ${label.toLowerCase()} from this device`}
          onClick={() => inputRef.current?.click()}
        >
          <Icon id="upload" />
          {busy ? "Working…" : "Upload photo"}
        </button>
        <button
          type="button"
          className="ghost"
          disabled={busy}
          title={`Take a ${label.toLowerCase()} now`}
          onClick={() => cameraRef.current?.click()}
        >
          <Icon id="camera" />
          Take photo
        </button>
        {canGuide && (
          <button
            type="button"
            className="ghost"
            disabled={busy}
            title={`Line the ${label.toLowerCase()} up against a frame first`}
            onClick={() => setGuideOpen(true)}
          >
            <Icon id="target" />
            Line up
          </button>
        )}
        <button
          type="button"
          className="ghost icon"
          title="Paste an image link"
          onClick={() => setLinkOpen(!linkOpen)}
        >
          <Icon id="link" />
        </button>
        <GuidedCamera
          open={guideOpen}
          square={square}
          onCapture={(file) => choose(file)}
          onClose={() => setGuideOpen(false)}
        />
        {value && removable && (
          <button
            type="button"
            className="ghost icon danger"
            title={`Remove this ${label.toLowerCase()}`}
            onClick={removeImage}
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
      {pending && (
        <PhotoCrop
          file={pending}
          onCancel={() => setPending(null)}
          onDone={(cropped) => {
            setPending(null);
            upload(cropped);
          }}
        />
      )}
    </div>
  );
}
