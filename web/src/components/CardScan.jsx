import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

/** Point the camera at a card and let the catalogue say which it is.
 *
 *  The same camera plumbing as BarcodeScan, and deliberately not the same
 *  loop. A barcode is decoded over and over until two frames agree, because
 *  the answer is exact and free to check. This is a photograph matched
 *  against twenty thousand others on the server, so it goes when you say it
 *  goes — one tap, one request.
 *
 *  What comes back is a short list, never one card. A fingerprint sees the
 *  artwork, and a reverse holo is the same picture as the normal print, so
 *  the last step is a person recognising their own card. That is also why
 *  the shot is kept on screen behind the results: choosing between four
 *  Charizards is easier with the one in your hand still showing.
 */

// A card is 63x88mm — 5:7 and change. The guide is that shape so what gets
// cropped is the card and not the table it is lying on, which is most of
// what a square crop would send.
const CARD_RATIO = 5 / 7;
const PREVIEW_RATIO = 3 / 4;   // the stage is portrait here, unlike a barcode
const REGION = 0.82;            // of the visible height
const SHOT_H = 640;             // enough for a fingerprint, small enough to post

const CAMERA = {
  audio: false,
  video: {
    facingMode: { ideal: "environment" },
    width: { ideal: 1920 },
    height: { ideal: 1080 },
  },
};

export default function CardScan({ onPick, title = "Scan a card" }) {
  const [open, setOpen] = useState(false);
  const [camError, setCamError] = useState(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState(null);
  const [shot, setShot] = useState(null);
  const [note, setNote] = useState(null);
  const videoRef = useRef(null);
  const trackRef = useRef(null);

  const secure = typeof window !== "undefined" && window.isSecureContext;

  useEffect(() => {
    if (!open || !secure) return;
    const video = videoRef.current;
    let dead = false;

    const teardown = () => {
      dead = true;
      const track = trackRef.current;
      if (track) {
        track.stop();
        trackRef.current = null;
      }
      if (video) video.srcObject = null;
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
      trackRef.current = stream.getVideoTracks()[0];
      video.srcObject = stream;
      try {
        await video.play();
      } catch {
        /* autoplay is allowed for a muted stream, but never assume */
      }
      if (!dead) setReady(true);
    })();

    return teardown;
  }, [open, secure]);

  /** The card out of the frame, as a JPEG small enough to post.
   *
   *  Cropped to the guide for the same reason the barcode scanner crops to
   *  its window: what the person aimed at is what should be asked about,
   *  and the rest of the room only makes the fingerprint worse.
   */
  const capture = () => {
    const video = videoRef.current;
    const vw = video?.videoWidth;
    const vh = video?.videoHeight;
    if (!vw || !vh) return null;
    // the preview is a portrait box filled with object-fit: cover, so part of
    // the frame is off-screen — crop from what is actually visible
    const wide = vw / vh > PREVIEW_RATIO;
    const visW = wide ? vh * PREVIEW_RATIO : vw;
    const visH = wide ? vh : vw / PREVIEW_RATIO;
    const sh = visH * REGION;
    const sw = sh * CARD_RATIO;
    const canvas = document.createElement("canvas");
    canvas.height = SHOT_H;
    canvas.width = Math.round(SHOT_H * CARD_RATIO);
    canvas
      .getContext("2d")
      .drawImage(video, (vw - sw) / 2, (vh - sh) / 2, sw, sh, 0, 0, canvas.width, canvas.height);
    return canvas;
  };

  const identify = async () => {
    const canvas = capture();
    if (!canvas) return;
    setBusy(true);
    setNote(null);
    setShot(canvas.toDataURL("image/jpeg", 0.7));
    try {
      const blob = await new Promise((r) => canvas.toBlob(r, "image/jpeg", 0.75));
      const { items } = await api.scanCard(blob);
      setResults(items || []);
      if (!items?.length) {
        setNote(
          "Nothing in the catalogue looks like that. Try filling the frame " +
            "with the card, or search by name instead."
        );
      }
    } catch (e) {
      setNote(e.message);
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    setOpen(false);
    setResults(null);
    setShot(null);
    setNote(null);
  };

  const choose = (card) => {
    close();
    onPick(card);
  };

  const modal = (
    <div className="modal-scrim" onClick={close}>
      <div className="modal cardscan" onClick={(e) => e.stopPropagation()}>
        <h2>{results ? "Which one is it?" : "Scan a card"}</h2>

        {!results && secure && !camError && (
          <>
            <div className="scan-stage tall">
              <video ref={videoRef} className="scan-video" muted playsInline autoPlay />
              <div className="card-guide" aria-hidden="true" />
            </div>
            <p>{ready ? "Fill the outline with the card" : "Starting the camera…"}</p>
            <button
              type="button"
              className="primary"
              disabled={!ready || busy}
              onClick={identify}
            >
              <Icon id="camera" />
              {busy ? "Looking…" : "Identify"}
            </button>
          </>
        )}

        {!results && (!secure || camError) && (
          <p>
            {camError
              ? `Camera failed (${camError}) — search by name instead.`
              : "Camera needs HTTPS (Tailscale serve) — search by name instead."}
          </p>
        )}

        {results && (
          <>
            {shot && <img className="scan-shot" src={shot} alt="" />}
            {results.length > 0 && (
              <div className="grid pick-grid">
                {results.map((c) => (
                  <div
                    key={c.id}
                    className="tile pick"
                    onClick={() => choose(c)}
                    title="This one"
                  >
                    {c.image_url ? (
                      <img src={c.image_url} alt={c.title} loading="lazy" />
                    ) : (
                      <div className="placeholder" data-label="no picture" />
                    )}
                    <div className="tile-info">
                      <strong>{c.title}</strong>
                      <small>{c.attrs?.set_name || ""}</small>
                      <small>{c.attrs?.card_number || ""}</small>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <button type="button" className="ghost" onClick={() => { setResults(null); setShot(null); setNote(null); }}>
              <Icon id="back" />
              Scan another
            </button>
          </>
        )}

        {note && <p className="sec-note">{note}</p>}
        <button type="button" className="ghost" onClick={close}>
          Cancel
        </button>
      </div>
    </div>
  );

  return (
    <>
      <button type="button" className="ghost icon" title={title} onClick={() => {
        setCamError(null);
        setReady(false);
        setOpen(true);
      }}>
        <Icon id="camera" />
      </button>
      {open && createPortal(modal, document.body)}
    </>
  );
}
