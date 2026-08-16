import { useState } from "react";
import { Icon } from "./Icons.jsx";
import { useAvailableModules, useSettings } from "../settings.jsx";

// Two questions, one screen: whose vault this is, and what's in it.
// Skipping is allowed — blank name keeps "Your Loot", and skipping the
// picker just enables everything.
export default function Onboarding() {
  const { save } = useSettings();
  // What this server carries. Offering a tile for a collection it does not
  // have invites somebody to pick it and then quietly drops the choice.
  const available = useAvailableModules();
  const [name, setName] = useState("");
  const [picked, setPicked] = useState(null); // null = not touched yet

  const [busy, setBusy] = useState(false);

  // Everything on until somebody says otherwise, but derived rather than
  // seeded into state — the list is empty on the first render, and state
  // seeded from it then would stay empty after the server answered.
  const chosen = picked ?? available.map((m) => m.key);
  const toggle = (key) =>
    setPicked(
      chosen.includes(key)
        ? chosen.filter((k) => k !== key)
        : [...chosen, key],
    );

  const finish = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await save({
        owner_name: name.trim(),
        enabled_modules: chosen.length ? chosen : available.map((m) => m.key),
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
          {available.map((m) => (
            <button
              key={m.key}
              type="button"
              className={`pick-tile ${chosen.includes(m.key) ? "on" : ""}`}
              onClick={() => toggle(m.key)}
              aria-pressed={chosen.includes(m.key)}
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
