import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { BrowserMultiFormatReader } from "@zxing/browser";
import { BarcodeFormat, DecodeHintType } from "@zxing/library";
import { Icon } from "./Icons.jsx";

// Scan button + modal. Camera decoding needs a secure context (HTTPS or
// localhost); everywhere else the modal still offers manual digit entry,
// which hits the exact same lookup.
// The modal renders through a portal: this component lives inside the
// add <form>, and a nested modal form would submit the outer one.

// Nothing we look up is ever a QR or Data Matrix, and a reader pays for every
// symbology it knows on every single frame. Six retail formats is the cheapest
// speed-up available.
const ZXING_FORMATS = [
  BarcodeFormat.EAN_13,
  BarcodeFormat.EAN_8,
  BarcodeFormat.UPC_A,
  BarcodeFormat.UPC_E,
  BarcodeFormat.CODE_128,
  // service and serial labels, which are not product barcodes at all
  BarcodeFormat.CODE_39,
  BarcodeFormat.ITF,
];
const NATIVE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "itf"];
const HINTS = new Map([[DecodeHintType.POSSIBLE_FORMATS, ZXING_FORMATS]]);

// Opt-in, for comics. A comic's main barcode is the same on every issue of a
// run — the issue lives in a separate five-digit symbol printed beside it. It
// isn't an inline add-on, so it has to be read as a barcode in its own right,
// and it is only offered where it means something: on a DVD or a game a stray
// five-digit read would just break the lookup.
const SUPPLEMENT_HINTS = new Map([
  [DecodeHintType.POSSIBLE_FORMATS, [...ZXING_FORMATS, BarcodeFormat.EAN_5]],
]);

// Cameras hand out 640x480 unless asked otherwise, and an EAN-13 printed down
// the spine of a DVD case simply isn't there at that resolution.
const CAMERA = {
  audio: false,
  video: {
    facingMode: { ideal: "environment" },
    width: { ideal: 1920 },
    height: { ideal: 1080 },
  },
};

// The window drawn over the preview, as a fraction of what you can see. Only
// these pixels are decoded: a third of the frame, so a third of the work, and
// the barcode next to the one you meant can't win the race.
const REGION = { w: 0.86, h: 0.42 };
const PREVIEW_RATIO = 4 / 3;
const WORK_W = 900; // decode at a fixed width, whatever the camera resolution

// Small items carry the squeezed 8-digit form, but every database we ask
// stores the full 12. Only ever called on a code the reader itself reported as
// UPC-E — an EAN-8 can look identical and must not be touched.
function expandUpcE(code) {
  if (!/^[01]\d{7}$/.test(code)) return code;
  const [n, a, b, c, d, e, f, check] = code;
  let body;
  if (f <= "2") body = `${a}${b}${f}0000${c}${d}${e}`;
  else if (f === "3") body = `${a}${b}${c}00000${d}${e}`;
  else if (f === "4") body = `${a}${b}${c}${d}00000${e}`;
  else body = `${a}${b}${c}${d}${e}0000${f}`;
  return n + body + check;
}

async function nativeFormats() {
  if (!("BarcodeDetector" in window)) return [];
  try {
    const all = await window.BarcodeDetector.getSupportedFormats();
    return NATIVE_FORMATS.filter((f) => all.includes(f));
  } catch {
    return [];
  }
}

export default function BarcodeScan({
  onCode,
  supplement = false,
  // What this particular button is pointed at. The decoder does not care —
  // a serial label is a Code 128 like any other — but the person holding the
  // phone does, and a scanner that says "barcode" while they aim at a serial
  // is asking them to guess whether it will work.
  title = "Scan a barcode",
  hint,
  // Product barcodes are digits and worth cleaning up; a serial is not. It
  // carries letters, and stripping them would hand back a number that looks
  // plausible and belongs to nothing.
  numeric = true,
}) {
  const [open, setOpen] = useState(false);
  const [manual, setManual] = useState("");
  const [camError, setCamError] = useState(null);
  const [ready, setReady] = useState(false);
  const [torch, setTorch] = useState(false);
  const [torchable, setTorchable] = useState(false);
  const videoRef = useRef(null);
  const trackRef = useRef(null);

  const secure = typeof window !== "undefined" && window.isSecureContext;

  useEffect(() => {
    if (!open || !secure) return;
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    let dead = false;
    let timer;
    let detect; // set once we know which decoder we got
    let pace = 16;
    let seen = null;
    let seenCount = 0;

    const teardown = () => {
      dead = true;
      clearTimeout(timer);
      const track = trackRef.current;
      if (track) {
        try {
          track.applyConstraints({ advanced: [{ torch: false }] });
        } catch {
          /* torch is best-effort everywhere */
        }
        track.stop();
        trackRef.current = null;
      }
      if (video) video.srcObject = null;
    };

    const grab = async () => {
      const vw = video.videoWidth;
      const vh = video.videoHeight;
      if (!vw || !vh) return null;
      // the preview is a 4:3 box filled with object-fit: cover, so some of the
      // frame is off-screen — crop from what's actually visible or the window
      // we drew would be lying about what it catches
      const wide = vw / vh > PREVIEW_RATIO;
      const visW = wide ? vh * PREVIEW_RATIO : vw;
      const visH = wide ? vh : vw / PREVIEW_RATIO;
      const sw = visW * REGION.w;
      const sh = visH * REGION.h;
      const cw = Math.min(WORK_W, Math.round(sw));
      const ch = Math.round((sh / sw) * cw);
      if (canvas.width !== cw || canvas.height !== ch) {
        canvas.width = cw;
        canvas.height = ch;
      }
      ctx.drawImage(video, (vw - sw) / 2, (vh - sh) / 2, sw, sh, 0, 0, cw, ch);
      return detect(canvas);
    };

    const tick = async () => {
      if (dead) return;
      let hit = null;
      try {
        hit = await grab();
      } catch {
        /* a dropped frame is not worth stopping the scan for */
      }
      if (dead) return;
      if (hit) {
        if (hit.text === seen) seenCount += 1;
        else {
          seen = hit.text;
          seenCount = 1;
        }
        // a single frame can misread; the same digits twice running can't, and
        // at 20-plus frames a second the second read costs nothing you'd feel
        if (seenCount >= 2) {
          const code = hit.upce ? expandUpcE(hit.text) : hit.text;
          navigator.vibrate?.(60);
          teardown();
          setOpen(false);
          onCode(code);
          return;
        }
      }
      // a plain timer, not requestAnimationFrame: decoding has nothing to do
      // with the display refresh, and rAF stops dead whenever the page isn't
      // compositing, which would strand the scan with the camera still lit
      timer = setTimeout(tick, pace);
    };

    (async () => {
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia(CAMERA);
      } catch (e) {
        if (!dead) setCamError(e?.message || "camera unavailable");
        return;
      }
      if (dead) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      const track = stream.getVideoTracks()[0];
      trackRef.current = track;
      setTorchable(!!track.getCapabilities?.().torch);
      video.srcObject = stream;
      try {
        await video.play();
      } catch {
        /* autoplay is allowed for a muted stream, but never assume */
      }
      if (dead) return;
      setReady(true);

      // the platform decoder has no EAN-5 at all, so supplement mode has to
      // go the long way round through zxing
      const supported = supplement ? [] : await nativeFormats();
      if (supported.length) {
        // the platform's own decoder, hardware-backed on phones
        const det = new window.BarcodeDetector({ formats: supported });
        detect = async (c) => {
          const [found] = await det.detect(c);
          return found ? { text: found.rawValue, upce: found.format === "upc_e" } : null;
        };
      } else {
        const reader = new BrowserMultiFormatReader(supplement ? SUPPLEMENT_HINTS : HINTS);
        detect = async (c) => {
          try {
            const r = reader.decodeFromCanvas(c);
            return { text: r.getText(), upce: r.getBarcodeFormat() === BarcodeFormat.UPC_E };
          } catch {
            return null; // nothing in this frame
          }
        };
        pace = 45; // this one decodes on the main thread: leave room to breathe
      }
      if (!dead) tick();
    })();

    return teardown;
  }, [open, secure]);

  const start = () => {
    setCamError(null);
    setReady(false);
    setTorch(false);
    setTorchable(false);
    setOpen(true);
  };

  const toggleTorch = async () => {
    const track = trackRef.current;
    if (!track) return;
    const next = !torch;
    try {
      await track.applyConstraints({ advanced: [{ torch: next }] });
      setTorch(next);
    } catch {
      setTorchable(false); // it claimed the capability and then refused
    }
  };

  const submitManual = () => {
    const value = numeric ? manual.replace(/\D/g, "") : manual.trim();
    if (value.length < (numeric ? (supplement ? 5 : 8) : 3)) return;
    setOpen(false);
    setManual("");
    onCode(value);
  };

  const modal = (
    <div className="modal-scrim" onClick={() => setOpen(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Scan the barcode</h2>
        {secure && !camError ? (
          <>
            <div className="scan-stage">
              <video ref={videoRef} className="scan-video" muted playsInline autoPlay />
              <div className="scan-frame" aria-hidden="true">
                <span className="scan-line" />
              </div>
              {torchable && (
                <button
                  type="button"
                  className={`scan-torch ${torch ? "on" : ""}`}
                  title={torch ? "Light off" : "Light on"}
                  onClick={toggleTorch}
                >
                  <Icon id="bolt" />
                </button>
              )}
            </div>
            <p>{ready ? "Fill the frame with the barcode" : "Starting the camera…"}</p>
          </>
        ) : (
          <p>
            {camError
              ? `Camera failed (${camError}) — type the digits instead.`
              : "Camera needs HTTPS (Tailscale serve) — type the digits under the barcode instead."}
          </p>
        )}
        <div className="form-row" style={{ width: "100%" }}>
          <input
            type="text"
            inputMode={numeric ? "numeric" : "text"}
            className="grow"
            placeholder={numeric ? "UPC/EAN digits" : "Type it instead"}
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submitManual();
              }
            }}
            autoFocus={!secure || !!camError}
          />
          <button type="button" className="primary icon" title="Look up" onClick={submitManual}>
            <Icon id="check" />
          </button>
        </div>
        <button type="button" className="ghost" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  );

  return (
    <>
      <button type="button" className="ghost icon" title={title} onClick={start}>
        <Icon id="scan" />
      </button>
      {open && createPortal(modal, document.body)}
    </>
  );
}
