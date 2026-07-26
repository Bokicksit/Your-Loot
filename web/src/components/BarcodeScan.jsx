import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { BrowserMultiFormatReader } from "@zxing/browser";
import { Icon } from "./Icons.jsx";

// Scan button + modal. Camera decoding needs a secure context (HTTPS or
// localhost); everywhere else the modal still offers manual digit entry,
// which hits the exact same lookup.
// The modal renders through a portal: this component lives inside the
// add <form>, and a nested modal form would submit the outer one.
export default function BarcodeScan({ onCode }) {
  const [open, setOpen] = useState(false);
  const [manual, setManual] = useState("");
  const [camError, setCamError] = useState(null);
  const videoRef = useRef(null);

  const secure = typeof window !== "undefined" && window.isSecureContext;

  useEffect(() => {
    if (!open || !secure) return;
    const reader = new BrowserMultiFormatReader();
    let controls;
    reader
      .decodeFromVideoDevice(undefined, videoRef.current, (result) => {
        if (result) {
          controls?.stop();
          setOpen(false);
          onCode(result.getText());
        }
      })
      .then((c) => (controls = c))
      .catch((e) => setCamError(e?.message || "camera unavailable"));
    return () => controls?.stop();
  }, [open, secure]);

  const submitManual = () => {
    const digits = manual.replace(/\D/g, "");
    if (digits.length < 8) return;
    setOpen(false);
    setManual("");
    onCode(digits);
  };

  const modal = (
    <div className="modal-scrim" onClick={() => setOpen(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Scan the barcode</h2>
        {secure && !camError ? (
          <video ref={videoRef} className="scan-video" muted playsInline />
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
            inputMode="numeric"
            className="grow"
            placeholder="UPC/EAN digits"
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
      <button type="button" className="ghost icon" title="Scan barcode" onClick={() => setOpen(true)}>
        <Icon id="scan" />
      </button>
      {open && createPortal(modal, document.body)}
    </>
  );
}
