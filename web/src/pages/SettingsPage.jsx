import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import { MODULES, useAvailableModules, useSettings } from "../settings.jsx";

const REGIONS = ["NTSC-U", "PAL", "NTSC-J", "Region-free"];
// mirrors the two book fields most shelves never change
const BOOK_FORMATS = ["Hardcover", "Paperback", "Trade Paperback", "Mass Market"];
const BOOK_JACKETS = ["With jacket", "No jacket"];

export default function SettingsPage() {
  const { settings, save } = useSettings();
  // what this server carries, not what the code can draw
  const available = useAvailableModules();
  const hasModule = (key) => available.some((m) => m.key === key);
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
          {available.map((m) => {
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

      {/* Every row here is a default for one collection, so each is drawn
          only where this server carries it — a "default region for games"
          on an install with no games configures nothing. The Pokédex toggle
          that used to live here is gone: the card list has its own, in the
          row above the cards it affects, which is where you actually reach
          for it. Two switches for one setting is one too many. */}
      {(hasModule("books") || hasModule("games") || hasModule("hardware")) && (
      <section className="settings-card">
        <h3>Display</h3>
        {hasModule("books") && (
          <div className="form-row">
            <span className="settings-label">Books are usually</span>
            <select
              value={settings.default_book_format}
              onChange={(e) => flash({ default_book_format: e.target.value })}
            >
              {BOOK_FORMATS.map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
            <select
              value={settings.default_book_jacket}
              onChange={(e) => flash({ default_book_jacket: e.target.value })}
            >
              {BOOK_JACKETS.map((j) => (
                <option key={j}>{j}</option>
              ))}
            </select>
          </div>
        )}
        {(hasModule("games") || hasModule("hardware")) && (
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
        )}
      </section>
      )}

      <ShareCard enabled={enabled} />
      <LockCard />
      <PlanCard />
      <AccountCard />
      <BackupCard />
      <PolicyLinks />

      {version && <p className="version-tag">Your Loot v{version}</p>}
    </div>
  );
}

const TOTAL = (r) => Object.values(r || {}).reduce((a, b) => a + b, 0);

const SIZE = (b) =>
  b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`;

/** Sharing is an export, not a link.
 *
 *  A link would need this server to be reachable from wherever the other
 *  person is, and most of these installs sit on a home network behind a
 *  router that has never been asked to forward anything. A file is sent the
 *  same way as any other file, works offline, and stops existing when they
 *  delete it — no public URL left listening after you have forgotten about
 *  it.
 */
function ShareCard({ enabled }) {
  const [images, setImages] = useState(true);
  const [busy, setBusy] = useState(null);
  const [note, setNote] = useState(null);
  const [error, setError] = useState(null);

  const scopes = [
    ...MODULES.filter((m) => enabled.includes(m.key)).map((m) => ({
      key: m.key,
      label: m.label,
      icon: m.icon,
    })),
    // the binder is a view of the cards, so it follows them on and off
    ...(enabled.includes("cards")
      ? [{ key: "pokedex", label: "Pokédex binder", icon: "card" }]
      : []),
    { key: "wanted", label: "Wanted list", icon: "star" },
  ];

  const download = async (scope, label) => {
    setBusy(scope);
    setError(null);
    setNote(null);
    try {
      const { blob, failed, filename } = await api.share(scope, images);
      // A blob URL rather than a direct link: the request needs its auth
      // header, so the file is already in hand by the time we save it.
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(href);
      setNote(
        `${label} — ${SIZE(blob.size)}` +
          (failed ? `, but ${failed} cover${failed === 1 ? "" : "s"} could not be fetched` : ""),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="settings-card">
      <h3>Share a collection</h3>
      <p>
        One HTML file holding a plain list — cover, title, and what shape it's
        in. Send it however you'd send a photo. It opens in any browser, works
        with no signal, and needs nothing installed at the other end.
      </p>
      <p className="settings-note">
        It's a copy, so it doesn't change when your collection does, and
        whoever has it keeps it. Your notes, tags, serial numbers and grading
        certificates are never in it.
      </p>
      <div className="form-row">
        <span className="settings-label">Include cover art</span>
        <button className={`toggle ${images ? "on" : ""}`} onClick={() => setImages(!images)}>
          {images ? "Included" : "Text only"}
        </button>
      </div>
      <p className="settings-note">
        {images
          ? "Pictures are shrunk and packed inside the file — a shelf is tens of KB, a full Pokédex binder about 2 MB."
          : "Names and details only. A full Pokédex binder comes to about 200 KB."}
      </p>
      <div className="form-row wrap">
        {scopes.map((s) => (
          <button
            key={s.key}
            className="ghost"
            disabled={!!busy}
            onClick={() => download(s.key, s.label)}
          >
            <Icon id={busy === s.key ? "save" : s.icon} />
            {busy === s.key ? "Building…" : s.label}
          </button>
        ))}
      </div>
      {note && (
        <p className="settings-note">
          <Icon id="check" /> {note}
        </p>
      )}
      {error && (
        <p className="error">
          <Icon id="alert" />
          {error}
        </p>
      )}
    </section>
  );
}

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

/** The plan, and the two buttons that change it.
 *
 *  Absent entirely where the server takes no payments, which is every
 *  self-hosted install — the person running it already paid, by running it,
 *  and an upgrade prompt on your own machine would be daft.
 *
 *  Cancelling is Stripe's page rather than one of ours, deliberately:
 *  somebody who wants to stop paying should not have to go through the
 *  people being paid.
 */
function PlanCard() {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // Both hooks at the top level and before any early return — React counts
  // them per render and a conditional one throws.
  const available = useAvailableModules();
  const { settings } = useSettings();

  useEffect(() => {
    api.billingStatus().then(setState).catch(() => setState({ available: false }));
  }, []);

  if (!state?.available) return null;

  const paidKeys = settings?.paid_modules || [];
  const paidModules = available.filter((m) => paidKeys.includes(m.key));

  const leave = async (call) => {
    setBusy(true);
    setError(null);
    try {
      const { url } = await call();
      window.location.href = url; // Stripe's page, not ours
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  const paying = state.plan === "supporter";
  const names = paidModules.map((m) => m.label).join(", ");

  return (
    <section className="settings-card">
      <h3>Your plan</h3>
      {paying ? (
        <>
          <p>
            You're on <strong>Supporter</strong>
            {state.plan_until
              ? ` — paid until ${new Date(state.plan_until).toLocaleDateString()}.`
              : "."}{" "}
            Thank you, genuinely.
          </p>
          {state.can_manage && (
            <button type="button" onClick={() => leave(api.billingPortal)} disabled={busy}>
              <Icon id="link" />
              {busy ? "…" : "Manage or cancel"}
            </button>
          )}
        </>
      ) : (
        <>
          <p>
            {state.limits?.applies && state.limits.cards
              ? `The free plan here holds ${state.limits.cards} cards, the first ${state.limits.dex} of the Pokédex and ${state.limits.binders} binder besides it.`
              : "You're on the free plan."}
            {names ? ` Supporter lifts all of that and adds ${names}, for $4 a month.` : ""}
          </p>
          <p className="settings-note">
            None of these limits exist in the software itself — run your own
            copy and there are none at all. They're here because this server,
            its database and your photographs cost money every month.
          </p>
          {/* Asked for here rather than at the payment page. A button that
              exists only to refuse you is worse than one that isn't there. */}
          {state.needs_confirmed_email ? (
            <>
              <p className="settings-note">
                Confirm your email address first — it's how a receipt and any
                renewal notice reach you. Check your inbox for the link, or
                send another from <strong>Your account</strong> below.
              </p>
              <button type="button" disabled>
                <Icon id="star" />
                Become a supporter
              </button>
            </>
          ) : (
            <button
              type="button"
              className="primary"
              onClick={() => leave(api.billingCheckout)}
              disabled={busy}
            >
              <Icon id="star" />
              {busy ? "…" : "Become a supporter"}
            </button>
          )}
        </>
      )}
      {error && (
        <p className="settings-note" style={{ color: "var(--danger, #ff8080)" }}>{error}</p>
      )}
      <p className="settings-note">
        Cancelling stops the next payment and leaves your plan running to the
        date you've paid for. Nothing is ever deleted, and you can take a copy
        of everything from Share a collection whether you're paying or not.
      </p>
    </section>
  );
}

/** Where the policies live, for somebody already inside.
 *
 *  They are public pages and the store listing links to them, but somebody
 *  wondering what happens to their photographs looks in settings, not in a
 *  store listing. Only where there are accounts — a self-hosted install has
 *  no operator to have a privacy policy about.
 */
function PolicyLinks() {
  const [me, setMe] = useState(null);
  useEffect(() => {
    api.authMe().then(setMe).catch(() => {});
  }, []);
  if (!me || !me.multi_user) return null;
  return (
    <section className="settings-card">
      {me.user?.is_admin && (
        <p className="settings-note" style={{ marginTop: 0 }}>
          <Link to="/admin">Admin — accounts and statistics</Link>
        </p>
      )}
      <h3>The small print</h3>
      <p className="settings-note" style={{ display: "flex", flexWrap: "wrap", gap: "8px 16px" }}>
        <a href="/help">How it works</a>
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms of service</a>
        <a href="/delete-account">Deleting your account</a>
      </p>
    </section>
  );
}

/** Your own account: the address, and the way out.
 *
 *  Only where there are accounts at all. A single-user install has no address
 *  to confirm and nowhere to go if it deleted itself — LockCard is the whole
 *  of its account settings.
 */
function AccountCard() {
  const [me, setMe] = useState(null);
  const [note, setNote] = useState(null);
  const [error, setError] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.authMe().then(setMe).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  if (!me || !me.multi_user || !me.user) return null;

  const user = me.user;
  // Only worth mentioning where a confirmation could actually be sent. On a
  // server with no mail provider there is nothing to confirm an address for
  // and no way to do it, so saying it is unconfirmed is a complaint about
  // something the person cannot fix.
  const confirmed = Boolean(user.email_verified_at) || !me.email_enabled;
  // The owner cannot leave — deleting account 1 leaves a database nobody can
  // sign into. Saying so beats a button that always fails.
  const isOwner = user.id === 1;

  const resend = async () => {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      await api.authResendVerification();
      setNote("Sent. Check your inbox — the link lasts a day.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.authDeleteMe(password);
      // everything is gone, including the session — start again from the gate
      window.location.href = "/";
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <section className="settings-card">
      <h3>Your account</h3>
      <p>
        Signed in as <strong>{user.email}</strong>
        {user.email_verified_at ? " — address confirmed." : "."}
      </p>

      {!confirmed && (
        <>
          <p className="settings-note">
            This address hasn't been confirmed yet. Until it is, we can't send
            you a link if you forget your password.
          </p>
          <button type="button" onClick={resend} disabled={busy}>
            <Icon id="check" />
            {busy ? "…" : "Send the confirmation again"}
          </button>
        </>
      )}

      {note && <p className="settings-note">{note}</p>}
      {error && (
        <p className="settings-note" style={{ color: "var(--danger, #ff8080)" }}>
          {error}
        </p>
      )}

      {/* There was no way out at all. On a shared machine that is not a
          missing convenience, it is the app refusing to let you leave. */}
      <button
        type="button"
        onClick={async () => {
          await api.authLogout().catch(() => {});
          window.location.href = "/";
        }}
      >
        <Icon id="back" />
        Sign out
      </button>

      <h4 style={{ margin: "18px 0 0", fontSize: "var(--f-2)" }}>Delete this account</h4>
      {isOwner ? (
        <p className="settings-note">
          This is the owner account, which can't be deleted — the server would
          be left with no way in. Another account can be removed from the users
          list.
        </p>
      ) : confirming ? (
        <form className="lock-form" onSubmit={remove}>
          <p className="settings-note">
            This removes your collection, photos, binders and wanted list. It
            cannot be undone — take a backup first if you want a copy.
          </p>
          <input
            type="password"
            placeholder="Your password, to be sure"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            autoFocus
          />
          <button type="submit" className="ghost danger" disabled={busy}>
            <Icon id="trash" />
            {busy ? "…" : "Delete everything"}
          </button>
          <button type="button" onClick={() => setConfirming(false)} disabled={busy}>
            Keep it
          </button>
        </form>
      ) : (
        <>
          <p className="settings-note">
            Removes the account and everything in it, for good.
          </p>
          <button type="button" onClick={() => setConfirming(true)}>
            <Icon id="trash" />
            Delete this account
          </button>
        </>
      )}
    </section>
  );
}

function BackupCard() {
  const fileInput = useRef(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [me, setMe] = useState(null);

  useEffect(() => {
    api.authMe().then(setMe).catch(() => {});
  }, []);

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

  // This is the whole database, not one person's collection — it holds every
  // account's items and restoring it replaces everything. So it belongs to
  // whoever runs the server, and on a service a subscriber must not be shown
  // a button that can only answer 403. Their own copy is "Share a collection"
  // above, which needs no permission and includes everything of theirs.
  if (me && me.multi_user && !me.user?.is_admin) return null;

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
