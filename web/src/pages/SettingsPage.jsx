import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { MODULES, useSettings } from "../settings.jsx";

const REGIONS = ["NTSC-U", "PAL", "NTSC-J", "Region-free"];

export default function SettingsPage() {
  const { settings, save } = useSettings();
  const [name, setName] = useState("");
  const [saved, setSaved] = useState(false);
  const [version, setVersion] = useState("");

  useEffect(() => {
    if (settings) setName(settings.owner_name || "");
  }, [settings?.owner_name]);

  useEffect(() => {
    api.health().then((h) => setVersion(h.version)).catch(() => {});
  }, []);

  if (!settings) return <p className="empty">Loading…</p>;

  const flash = async (patch) => {
    await save(patch);
    setSaved(true);
    setTimeout(() => setSaved(false), 1400);
  };

  const enabled = settings.enabled_modules || [];

  const toggleModule = (key) => {
    const next = enabled.includes(key)
      ? enabled.filter((k) => k !== key)
      : [...enabled, key];
    if (!next.length) return; // keep at least one collection
    flash({ enabled_modules: next });
  };


  return (
    <div className="settings">
      <div className="toolbar">
        <h2 style={{ margin: 0, fontSize: "var(--f-5)" }}>Settings</h2>
        {saved && <span className="saved-flash">saved</span>}
      </div>

      <section className="settings-card">
        <h3>Collector name</h3>
        <p>Shown in the header — “{name.trim() || "Your"}’s Loot”.</p>
        <div className="form-row">
          <input
            type="text"
            className="grow"
            maxLength={50}
            placeholder="Leave blank for “Your Loot”"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => name !== (settings.owner_name || "") && flash({ owner_name: name.trim() })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
        </div>
      </section>

      <section className="settings-card">
        <h3>Collections</h3>
        <p>
          What's on here is what's on the Collections tab. Turn off what you
          don't collect and it goes — nothing is deleted, the items stay in the
          database and stop appearing anywhere, and turning it back on returns
          everything exactly as it was.
        </p>
        <div className="settings-modules">
          {MODULES.map((m) => {
            const on = enabled.includes(m.key);
            return (
              <div key={m.key} className={`module-row ${on ? "" : "off"}`}>
                <Icon id={m.icon} />
                <span className="sheet-text">
                  <strong>{m.label}</strong>
                  <small>{m.blurb}</small>
                </span>
                <button
                  className={`toggle ${on ? "on" : ""}`}
                  onClick={() => toggleModule(m.key)}
                >
                  {on ? "On" : "Off"}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      <section className="settings-card">
        <h3>Display</h3>
        <div className="form-row">
          <span className="settings-label">Pokédex slots per row</span>
          <span className="col-picker">
            {[3, 4, 5].map((n) => (
              <button
                key={n}
                className={`chip ${settings.dex_cols === n ? "active" : ""}`}
                onClick={() => flash({ dex_cols: n })}
              >
                {n}
              </button>
            ))}
          </span>
        </div>
        <div className="form-row">
          <span className="settings-label">Cards per row</span>
          <span className="col-picker">
            {[3, 4, 5].map((n) => (
              <button
                key={n}
                className={`chip ${settings.card_cols === n ? "active" : ""}`}
                onClick={() => flash({ card_cols: n })}
              >
                {n}
              </button>
            ))}
          </span>
        </div>
        <div className="form-row">
          <span className="settings-label">Show Pokédex cards in the card list</span>
          <button
            className={`toggle ${settings.show_binder_in_collection ? "on" : ""}`}
            onClick={() =>
              flash({ show_binder_in_collection: !settings.show_binder_in_collection })
            }
          >
            {settings.show_binder_in_collection ? "Shown" : "Hidden"}
          </button>
        </div>
        <div className="form-row">
          <span className="settings-label">
            Default region for new games &amp; hardware
          </span>
          <select
            value={settings.default_region}
            onChange={(e) => flash({ default_region: e.target.value })}
          >
            {REGIONS.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>
      </section>

      <LockCard />
      <BackupCard />

      {version && <p className="version-tag">Your Loot v{version}</p>}
    </div>
  );
}

const TOTAL = (r) => Object.values(r || {}).reduce((a, b) => a + b, 0);

/** Radarr and Sonarr put this in settings rather than in a config file, and
 *  they're right to: turning the lock on is a decision you make once you've
 *  already got the app open, not something you want to restart a container
 *  for. */
function LockCard() {
  const [me, setMe] = useState(null);
  const [secret, setSecret] = useState("");
  const [current, setCurrent] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const [error, setError] = useState(null);

  const load = () => api.authMe().then(setMe).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  // Accounts mode has its own screen for this; here we only handle the
  // one-account case, where the whole feature is "is there a password".
  if (!me || me.multi_user) return null;

  const save = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      await api.changePassword({
        current_password: current || null,
        new_password: secret || null,
      });
      setSecret("");
      setCurrent("");
      setNote(secret ? "Locked. You'll be asked for this next time." : "Lock removed.");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="settings-card">
      <h3>Lock this app</h3>
      <p>
        {me.locked
          ? "This app asks for a password before it opens."
          : "Anyone who can reach this app can see and edit your collection. " +
            "Set a password — or a short PIN, which is easier on a phone — and " +
            "it will ask first."}
      </p>
      <form className="lock-form" onSubmit={save}>
        {me.locked && (
          <input
            type="password"
            placeholder="Current password or PIN"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            autoComplete="current-password"
            required
          />
        )}
        <input
          type="password"
          placeholder={me.locked ? "New — or blank to remove the lock" : "Password or PIN (4+)"}
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          autoComplete="new-password"
          minLength={secret ? 4 : undefined}
        />
        <button type="submit" className="primary" disabled={busy}>
          <Icon id="check" />
          {busy ? "…" : me.locked && !secret ? "Remove lock" : "Save"}
        </button>
      </form>
      {note && <p className="settings-note">{note}</p>}
      {error && (
        <p className="settings-note" style={{ color: "var(--danger, #ff8080)" }}>
          {error}
        </p>
      )}
      <p className="settings-note">
        It protects the app, not the data — anyone with access to the server
        can still read the database. Locked out? Run{" "}
        <code>docker compose exec api python -m app.resetpw --clear</code> on
        the host.
      </p>
    </section>
  );
}

function BackupCard() {
  const fileInput = useRef(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const pick = (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // let the same file be picked again after an error
    if (!file) return;
    if (
      !confirm(
        `Restore from ${file.name}?\n\n` +
          "This REPLACES your whole collection — everything currently in Your " +
          "Loot is deleted and rebuilt from the backup. Anything added since " +
          "the backup was taken will be gone.\n\n" +
          "Take a backup first if you're not sure."
      )
    )
      return;
    restore(file);
  };

  const restore = async (file) => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.restoreBackup(file));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="settings-card">
      <h3>Backup &amp; restore</h3>
      <p>
        A backup is a single zip holding your whole collection — every item,
        every copy with its condition, the wanted list, the Pokédex, your
        settings, and the photos you've uploaded. Keep one somewhere that isn't
        this server.
      </p>
      <div className="form-row wrap">
        <a className="primary" href={api.backupUrl} download>
          <Icon id="save" />
          Download backup
        </a>
        <button className="ghost" disabled={busy} onClick={() => fileInput.current?.click()}>
          <Icon id="upload" />
          {busy ? "Restoring…" : "Restore from a backup…"}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".zip,application/zip"
          style={{ display: "none" }}
          onChange={pick}
        />
      </div>

      {error && (
        <p className="error">
          <Icon id="alert" />
          {error}
        </p>
      )}

      {result && (
        <div className="restore-result">
          <strong>
            <Icon id="check" />
            Restored {TOTAL(result.restored).toLocaleString()} rows
            {result.images ? ` and ${result.images} images` : ""}
          </strong>
          <small>
            From a backup taken
            {result.created_at ? ` ${result.created_at.replace("T", " ")}` : ""}
            {result.from_version ? ` on v${result.from_version}` : ""}.
          </small>
          <button className="primary" onClick={() => window.location.reload()}>
            Reload to see it
          </button>
        </div>
      )}
    </section>
  );
}
