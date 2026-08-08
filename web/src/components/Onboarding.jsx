import { useState } from "react";
import { Icon } from "./Icons.jsx";
import { MODULES, useSettings } from "../settings.jsx";

// Two questions, one screen: whose vault this is, and what's in it.
// Skipping is allowed — blank name keeps "Your Loot", and skipping the
// picker just enables everything.
export default function Onboarding() {
  const { save } = useSettings();
  const [name, setName] = useState("");
  const [picked, setPicked] = useState(MODULES.map((m) => m.key));
  const [busy, setBusy] = useState(false);

  const toggle = (key) =>
    setPicked((p) => (p.includes(key) ? p.filter((k) => k !== key) : [...p, key]));

  const finish = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await save({
        owner_name: name.trim(),
        enabled_modules: picked.length ? picked : MODULES.map((m) => m.key),
      });
    } catch (e) {
      alert(e.message);
      setBusy(false);
    }
  };

  return (
    <div className="modal-scrim">
      <form
        className="modal onboarding"
        onSubmit={(e) => {
          e.preventDefault();
          finish();
        }}
      >
        <span className="glyph"><Icon id="coin" /></span>
        <h2>Whose hoard is this?</h2>
        <p>Your name goes on the vault door. Leave it blank if you'd rather not.</p>
        <input
          type="text"
          maxLength={50}
          autoFocus
          placeholder="Collector name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <h2 style={{ marginTop: "var(--s-3)" }}>And what are you hoarding?</h2>
        <p>Turn off anything you don't collect — you can change this later.</p>
        <div className="onboard-picks">
          {MODULES.map((m) => (
            <button
              key={m.key}
              type="button"
              className={`pick-tile ${picked.includes(m.key) ? "on" : ""}`}
              onClick={() => toggle(m.key)}
              aria-pressed={picked.includes(m.key)}
            >
              <Icon id={m.icon} />
              <strong>{m.label}</strong>
              <small>{m.blurb}</small>
            </button>
          ))}
        </div>

        <button type="submit" className="primary" disabled={busy}>
          {name.trim() ? `Open ${name.trim()}’s Loot` : "Open the vault"}
        </button>
      </form>
    </div>
  );
}
