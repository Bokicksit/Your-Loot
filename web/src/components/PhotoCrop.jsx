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
  const [crop, setCrop] = useState({ x: 0, y: 0, w: 1, h: 1 });
  const [angle, setAngle] = useState(0); // degrees; straightens a tilted shot
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [autoNote, setAutoNote] = useState(null);
  const imgRef = useRef(null); // the decoded photo, never rendered directly
  const canvasRef = useRef(null); // what's on screen — drawn, so it can rotate
  const dragRef = useRef(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      setReady(true);
    };
    img.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);

  /** Size of the photo's bounding box once rotated — a tilted rectangle needs
   *  more room than it started with. */
  const rotatedSize = () => {
    const img = imgRef.current;
    const r = (angle * Math.PI) / 180;
    const c = Math.abs(Math.cos(r));
    const s = Math.abs(Math.sin(r));
    return {
      w: img.naturalWidth * c + img.naturalHeight * s,
      h: img.naturalWidth * s + img.naturalHeight * c,
    };
  };

  /** Draw the rotated photo into `canvas` at the given output width/height.
   *  Preview and export both go through here, so they can't drift apart. */
  const paint = (canvas, outW, outH, fill = "#0b0a0e") => {
    const img = imgRef.current;
    canvas.width = Math.max(1, Math.round(outW));
    canvas.height = Math.max(1, Math.round(outH));
    const { w } = rotatedSize();
    const scale = canvas.width / w;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = fill; // the corners a rotation exposes
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((angle * Math.PI) / 180);
    ctx.drawImage(
      img,
      (-img.naturalWidth * scale) / 2,
      (-img.naturalHeight * scale) / 2,
      img.naturalWidth * scale,
      img.naturalHeight * scale
    );
    ctx.restore();
  };

  // repaint the preview whenever the photo or its angle changes
  useEffect(() => {
    if (!ready || !canvasRef.current) return;
    const { w, h } = rotatedSize();
    const box = canvasRef.current.parentElement.getBoundingClientRect();
    const maxW = box.width || 480;
    const maxH = Math.min(window.innerHeight * 0.5, 460);
    const fit = Math.min(maxW / w, maxH / h, 1);
    paint(canvasRef.current, w * fit, h * fit);
  }, [ready, angle]);

  /** Best-effort "snap to the item". Reads the border colour as the background
   *  and walks in from each edge until a row or column stops looking like it.
   *  Reliable for a card on a desk; a busy background defeats it, which is why
   *  the handles are still there. */
  const autoCrop = () => {
    const img = imgRef.current;
    if (!img) return;

    // The background is sampled from the UNROTATED photo. Rotating exposes
    // corners that aren't part of the picture, and if those were sampled they'd
    // read as "the item" and drag the box back out to the full frame.
    const probe = document.createElement("canvas");
    const ps = Math.min(120 / img.naturalWidth, 120 / img.naturalHeight, 1);
    probe.width = Math.max(1, Math.round(img.naturalWidth * ps));
    probe.height = Math.max(1, Math.round(img.naturalHeight * ps));
    const pctx = probe.getContext("2d", { willReadFrequently: true });
    pctx.drawImage(img, 0, 0, probe.width, probe.height);
    const pd = pctx.getImageData(0, 0, probe.width, probe.height).data;
    const ppx = (x, y) => {
      const i = (y * probe.width + x) * 4;
      return [pd[i], pd[i + 1], pd[i + 2]];
    };
    const edge = [];
    for (let x = 0; x < probe.width; x++) edge.push(ppx(x, 0), ppx(x, probe.height - 1));
    for (let y = 0; y < probe.height; y++) edge.push(ppx(0, y), ppx(probe.width - 1, y));
    // median, not mean — a corner of the item poking into the frame shifts an
    // average but barely moves a median
    const bg = [0, 1, 2].map((k) => {
      const vals = edge.map((p) => p[k]).sort((a, b) => a - b);
      return vals[Math.floor(vals.length / 2)];
    });

    // now measure against the rotated view, filling the exposed corners with
    // that same background so they read as empty space
    const { w: rw, h: rh } = rotatedSize();
    const S = 260; // a thumbnail — full resolution buys nothing here
    const scale = Math.min(S / rw, S / rh, 1);
    const w = Math.max(1, Math.round(rw * scale));
    const h = Math.max(1, Math.round(rh * scale));
    const canvas = document.createElement("canvas");
    paint(canvas, w, h, `rgb(${bg[0]},${bg[1]},${bg[2]})`);
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const { data } = ctx.getImageData(0, 0, w, h);
    const px = (x, y) => {
      const i = (y * w + x) * 4;
      return [data[i], data[i + 1], data[i + 2]];
    };

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

  // offer a crop as soon as the photo is decoded; straightening afterwards
  // leaves the box where it is rather than yanking it about
  useEffect(() => {
    if (ready) autoCrop();
  }, [ready]);

  const startDrag = (mode) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    const box = canvasRef.current.getBoundingClientRect();
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
    if (!imgRef.current || busy) return;
    setBusy(true);
    // rotate at full resolution first, then take the crop out of that — so a
    // straightened photo loses nothing a straight one wouldn't
    const { w: rw, h: rh } = rotatedSize();
    const rotated = document.createElement("canvas");
    paint(rotated, rw, rh);
    const sx = Math.round(crop.x * rw);
    const sy = Math.round(crop.y * rh);
    const sw = Math.max(1, Math.round(crop.w * rw));
    const sh = Math.max(1, Math.round(crop.h * rh));
    const canvas = document.createElement("canvas");
    canvas.width = sw;
    canvas.height = sh;
    canvas.getContext("2d").drawImage(rotated, sx, sy, sw, sh, 0, 0, sw, sh);
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
          <canvas ref={canvasRef} className="crop-img" />
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

        {/* straighten a shot taken at an angle. The crop stays square to the
            screen — rotating the photo under it is how every photo editor does
            this, and it keeps the exported image un-skewed. */}
        <div className="crop-rotate">
          <button
            type="button"
            className="ghost icon"
            title="Rotate a quarter turn left"
            onClick={() => setAngle((a) => ((a - 90 + 360) % 360) - (((a - 90 + 360) % 360) > 180 ? 360 : 0))}
          >
            ⟲
          </button>
          <input
            type="range"
            min="-45"
            max="45"
            step="0.5"
            value={((angle + 180) % 360) - 180 >= -45 && ((angle + 180) % 360) - 180 <= 45
              ? ((angle + 180) % 360) - 180
              : 0}
            onChange={(e) => setAngle(Number(e.target.value))}
            aria-label="Straighten"
          />
          <button
            type="button"
            className="ghost icon"
            title="Rotate a quarter turn right"
            onClick={() => setAngle((a) => ((a + 90 + 360) % 360) - (((a + 90 + 360) % 360) > 180 ? 360 : 0))}
          >
            ⟳
          </button>
          <b>{Math.round(angle)}°</b>
        </div>

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
