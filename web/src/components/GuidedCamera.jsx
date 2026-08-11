import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icons.jsx";

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

export default function GuidedCamera({ open, square = false, onCapture, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [error, setError] = useState(null);
  const [ready, setReady] = useState(false);

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

  const capture = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const { x, y, w, h } = frameIn(video.videoWidth, video.videoHeight);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w);
    canvas.height = Math.round(h);
    canvas.getContext("2d").drawImage(video, x, y, w, h, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        onCapture(new File([blob], `photo-${Date.now()}.jpg`, { type: "image/jpeg" }));
        onClose();
      },
      "image/jpeg",
      0.92
    );
  };

  if (!open) return null;

  return (
    <div className="cam-sheet" role="dialog" aria-label="Line up the photo">
      <div className="cam-stage">
        <video ref={videoRef} className="cam-video" muted playsInline autoPlay />
        {/* Drawn over the video rather than composed into it: this is a
            viewfinder marking, and it must never end up in the picture. */}
        <div
          className={`cam-guide ${square ? "square" : ""} ${ready ? "" : "waiting"}`}
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

      <div className="cam-bar">
        <button type="button" className="ghost" onClick={onClose}>
          Cancel
        </button>
        <span className="cam-hint">
          {error ? "" : "Line the edges up with the frame"}
        </span>
        <button
          type="button"
          className="primary icon cam-shutter"
          onClick={capture}
          disabled={!ready || !!error}
          title="Take the picture"
        >
          <Icon id="camera" />
        </button>
      </div>
    </div>
  );
}
