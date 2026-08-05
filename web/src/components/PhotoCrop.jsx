import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icons.jsx";

// Crop a photo before it's uploaded. Free-form: a card, a sleeve and a console
// box are all different shapes, so forcing an aspect ratio would just make
// people fight it.
//
// The crop is kept as fractions of the image (0–1) rather than pixels, so it
// survives the picture being displayed at whatever size the screen allows.

const MIN = 0.06; // a crop can't be smaller than this fraction, or it vanishes

export default function PhotoCrop({ file, onDone, onCancel }) {
  const [src, setSrc] = useState(null);
  const [crop, setCrop] = useState({ x: 0, y: 0, w: 1, h: 1 });
  const [busy, setBusy] = useState(false);
  const [autoNote, setAutoNote] = useState(null);
  const imgRef = useRef(null);
  const dragRef = useRef(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  /** Best-effort "snap to the item". Reads the border colour as the background
   *  and walks in from each edge until a row or column stops looking like it.
   *  Reliable for a card on a desk; a busy background defeats it, which is why
   *  the handles are still there. */
  const autoCrop = () => {
    const img = imgRef.current;
    if (!img) return;
    const S = 260; // work on a thumbnail — full resolution buys nothing here
    const scale = Math.min(S / img.naturalWidth, S / img.naturalHeight, 1);
    const w = Math.max(1, Math.round(img.naturalWidth * scale));
    const h = Math.max(1, Math.round(img.naturalHeight * scale));
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, w, h);
    const { data } = ctx.getImageData(0, 0, w, h);
    const px = (x, y) => {
      const i = (y * w + x) * 4;
      return [data[i], data[i + 1], data[i + 2]];
    };

    // median of the frame's pixels — a median ignores the corner of the item
    // poking into the border better than an average would
    const edge = [];
    for (let x = 0; x < w; x++) edge.push(px(x, 0), px(x, h - 1));
    for (let y = 0; y < h; y++) edge.push(px(0, y), px(w - 1, y));
    const bg = [0, 1, 2].map((k) => {
      const vals = edge.map((p) => p[k]).sort((a, b) => a - b);
      return vals[Math.floor(vals.length / 2)];
    });

    const differs = (x, y) => {
      const p = px(x, y);
      return (
        Math.abs(p[0] - bg[0]) + Math.abs(p[1] - bg[1]) + Math.abs(p[2] - bg[2]) > 105
      );
    };
    // a whole row has to disagree, not one speck of dust or a shadow
    const rowHit = (y) => {
      let n = 0;
      for (let x = 0; x < w; x++) if (differs(x, y)) n++;
      return n / w >= 0.06;
    };
    const colHit = (x) => {
      let n = 0;
      for (let y = 0; y < h; y++) if (differs(x, y)) n++;
      return n / h >= 0.06;
    };

    let top = 0, bottom = h - 1, left = 0, right = w - 1;
    while (top < bottom && !rowHit(top)) top++;
    while (bottom > top && !rowHit(bottom)) bottom--;
    while (left < right && !colHit(left)) left++;
    while (right > left && !colHit(right)) right--;

    const cw = (right - left + 1) / w;
    const ch = (bottom - top + 1) / h;
    if (cw < 0.15 || ch < 0.15 || (cw > 0.97 && ch > 0.97)) {
      setAutoNote("Couldn't pick out an edge — drag the corners instead.");
      return;
    }
    const pad = 0.006; // a hair of breathing room so nothing is shaved off
    setCrop({
      x: Math.max(0, left / w - pad),
      y: Math.max(0, top / h - pad),
      w: Math.min(1 - Math.max(0, left / w - pad), cw + pad * 2),
      h: Math.min(1 - Math.max(0, top / h - pad), ch + pad * 2),
    });
    setAutoNote(null);
  };

  const startDrag = (mode) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    const box = imgRef.current.getBoundingClientRect();
    dragRef.current = { mode, box, startX: e.clientX, startY: e.clientY, crop };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };

  const onMove = (e) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = (e.clientX - d.startX) / d.box.width;
    const dy = (e.clientY - d.startY) / d.box.height;
    const c = { ...d.crop };
    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

    if (d.mode === "move") {
      c.x = clamp(d.crop.x + dx, 0, 1 - d.crop.w);
      c.y = clamp(d.crop.y + dy, 0, 1 - d.crop.h);
    } else {
      // each corner moves its own two edges; the opposite corner stays put
      if (d.mode.includes("w")) {
        const x = clamp(d.crop.x + dx, 0, d.crop.x + d.crop.w - MIN);
        c.w = d.crop.w + (d.crop.x - x);
        c.x = x;
      }
      if (d.mode.includes("e")) {
        c.w = clamp(d.crop.w + dx, MIN, 1 - d.crop.x);
      }
      if (d.mode.includes("n")) {
        const y = clamp(d.crop.y + dy, 0, d.crop.y + d.crop.h - MIN);
        c.h = d.crop.h + (d.crop.y - y);
        c.y = y;
      }
      if (d.mode.includes("s")) {
        c.h = clamp(d.crop.h + dy, MIN, 1 - d.crop.y);
      }
    }
    setCrop(c);
  };

  const endDrag = () => {
    dragRef.current = null;
  };

  const confirm = () => {
    const img = imgRef.current;
    if (!img || busy) return;
    setBusy(true);
    const sx = Math.round(crop.x * img.naturalWidth);
    const sy = Math.round(crop.y * img.naturalHeight);
    const sw = Math.max(1, Math.round(crop.w * img.naturalWidth));
    const sh = Math.max(1, Math.round(crop.h * img.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = sw;
    canvas.height = sh;
    canvas.getContext("2d").drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh);
    canvas.toBlob(
      (blob) => {
        setBusy(false);
        if (!blob) return onDone(file); // nothing lost — send the original
        const name = (file.name || "photo").replace(/\.[^.]+$/, "") + ".jpg";
        onDone(new File([blob], name, { type: "image/jpeg" }));
      },
      "image/jpeg",
      0.92
    );
  };

  const pct = (n) => `${n * 100}%`;
  const modal = (
    <div className="modal-scrim" onClick={onCancel}>
      <div className="modal crop-modal" onClick={(e) => e.stopPropagation()}>
        <h2>Trim the photo</h2>
        <div
          className="crop-stage"
          onPointerMove={onMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          {src && (
            <img
              ref={imgRef}
              src={src}
              alt=""
              className="crop-img"
              onLoad={autoCrop}
              draggable="false"
            />
          )}
          <div
            className="crop-box"
            style={{ left: pct(crop.x), top: pct(crop.y), width: pct(crop.w), height: pct(crop.h) }}
            onPointerDown={startDrag("move")}
          >
            {["nw", "ne", "sw", "se"].map((corner) => (
              <span
                key={corner}
                className={`crop-handle ${corner}`}
                onPointerDown={startDrag(corner)}
              />
            ))}
          </div>
        </div>
        {autoNote && <p className="crop-note">{autoNote}</p>}
        <div className="form-row wrap" style={{ width: "100%" }}>
          <button type="button" className="ghost" onClick={autoCrop}>
            <Icon id="scan" />
            Snap to edges
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => setCrop({ x: 0, y: 0, w: 1, h: 1 })}
          >
            Whole photo
          </button>
          <button
            type="button"
            className="primary"
            onClick={confirm}
            disabled={busy}
            style={{ marginLeft: "auto" }}
          >
            <Icon id="check" />
            {busy ? "Trimming…" : "Use photo"}
          </button>
          <button type="button" className="ghost" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
