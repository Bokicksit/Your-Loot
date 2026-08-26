import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icons.jsx";
import { keepFocusing, scratchCanvas, sharpestOf } from "../focus.js";

/* Line the thing up before you shoot it.
 *
 * The ordinary "Take photo" button hands off to the phone's own camera app,
 * which takes better pictures than we ever will — better focus, better
 * exposure, and a shutter people already know. It gives us nowhere to draw,
 * though, so a card photographed a few degrees off stays a few degrees off
 * until the cropper straightens it by hand.
 *
 * This is the other option, not a replacement: a live view with a frame to
 * square the item against, and a capture that keeps only what is inside it.
 * Getting the edges parallel here is much easier than fixing the rotation
 * afterwards.
 *
 * Needs a secure context, like every getUserMedia in this app. On a plain-http
 * LAN it simply is not offered, and the native camera still is.
 */

const FRAME_INSET = 0.86; // the frame fills most of the view, not all of it

export default function GuidedCamera({
  open,
  square = false,
  onCapture,
  onClose,
  onUseNative,
}) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);
  // Off turns this into an ordinary camera: no frame drawn, and the whole
  // view captured rather than the frame's worth of it. The drawing and the
  // crop are the same decision, so one switch governs both.
  const [guides, setGuides] = useState(true);
  // the shutter takes a burst and keeps the sharpest of it, so this says so
  const [shooting, setShooting] = useState(false);
  const scratchRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    let dead = false;

    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: "environment" },
            // ask for something worth cropping out of; the browser gives what
            // it can rather than failing when the camera cannot manage it
            width: { ideal: 2560 },
            height: { ideal: 1440 },
          },
          audio: false,
        });
        if (dead) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        // A photograph somebody keeps deserves the lens still hunting: this
        // view is held at arm's length over a table and the distance changes
        // the whole time. Best-effort — see focus.js.
        await keepFocusing(stream.getVideoTracks()[0]);
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => {});
        }
        setReady(true);
      } catch (e) {
        setError(
          e?.name === "NotAllowedError"
            ? "The camera was blocked. Allow it for this site, or use Take photo instead."
            : "No camera available here — use Take photo instead."
        );
      }
    })();

    return () => {
      dead = true;
      setReady(false);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
  }, [open]);

  /** The guide rectangle, in the video's own pixels. The overlay and the crop
   *  are worked out from the same numbers, so what you framed is what you
   *  get — a frame that only decorated the screen would be a lie. */
  const frameIn = (w, h) => {
    const ratio = square ? 1 : 0.72; // cards, cases and books are all near this
    let fw = w * FRAME_INSET;
    let fh = fw / ratio;
    if (fh > h * FRAME_INSET) {
      fh = h * FRAME_INSET;
      fw = fh * ratio;
    }
    return { x: (w - fw) / 2, y: (h - fh) / 2, w: fw, h: fh };
  };

  /** One frame, cropped to the guide. */
  const grab = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return null;
    const { x, y, w, h } = guides
      ? frameIn(video.videoWidth, video.videoHeight)
      : { x: 0, y: 0, w: video.videoWidth, h: video.videoHeight };
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w);
    canvas.height = Math.round(h);
    canvas.getContext("2d").drawImage(video, x, y, w, h, 0, 0, canvas.width, canvas.height);
    return canvas;
  };

  /** The shutter.
   *
   *  Five frames over about half a second, and the sharpest is the one kept.
   *  Pressing the button means "take a good picture of this", not "freeze
   *  exactly this instant" — the second is what it used to mean, and why a
   *  small movement produced a photo that looked fine until you opened it.
   *  Fewer frames than the card scanner takes: these are full-resolution and
   *  the person is watching a shutter, so the wait has to stay short.
   */
  const capture = async () => {
    if (shooting) return;
    setShooting(true);
    try {
      if (!scratchRef.current) {
        scratchRef.current = scratchCanvas(square ? 1 : 0.72);
      }
      const canvas = await sharpestOf(grab, scratchRef.current, 5, 90);
      if (!canvas) return;
      const blob = await new Promise((r) => canvas.toBlob(r, "image/jpeg", 0.92));
      if (!blob) return;
      onCapture(new File([blob], `photo-${Date.now()}.jpg`, { type: "image/jpeg" }));
      onClose();
    } finally {
      setShooting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="cam-sheet" role="dialog" aria-label="Line up the photo">
      <div className="cam-stage">
        <video ref={videoRef} className="cam-video" muted playsInline autoPlay />
        {/* Drawn over the video rather than composed into it: this is a
            viewfinder marking, and it must never end up in the picture. */}
        <div
          className={`cam-guide ${square ? "square" : ""} ${
            ready && guides ? "" : "waiting"
          }`}
          aria-hidden="true"
        >
          <span className="cam-corner tl" />
          <span className="cam-corner tr" />
          <span className="cam-corner bl" />
          <span className="cam-corner br" />
          <span className="cam-third v" />
          <span className="cam-third h" />
        </div>
        {error && <p className="cam-error">{error}</p>}
      </div>

      <div className="cam-top">
        <button
          type="button"
          className={`chip ${guides ? "active" : ""}`}
          onClick={() => setGuides(!guides)}
          aria-pressed={guides}
        >
          <Icon id="target" />
          Guides
        </button>
        {onUseNative && (
          <button type="button" className="chip" onClick={onUseNative}>
            <Icon id="camera" />
            Phone camera
          </button>
        )}
      </div>

      <div className="cam-bar">
        <button type="button" className="ghost" onClick={onClose}>
          Cancel
        </button>
        <span className="cam-hint">
          {error
            ? ""
            : shooting
              ? "Holding still for a sharp one…"
              : guides
                ? "Line the edges up with the frame"
                : "Guides off — the whole view is kept"}
        </span>
        <button
          type="button"
          className="primary icon cam-shutter"
          onClick={capture}
          disabled={!ready || !!error || shooting}
          title={shooting ? "Waiting for a sharp frame…" : "Take the picture"}
        >
          <Icon id="camera" />
        </button>
      </div>
    </div>
  );
}
