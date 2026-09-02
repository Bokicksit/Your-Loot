import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";
import {
  MODULES,
  useAvailableModules,
  usePublicProfiles,
  useSettings,
} from "../settings.jsx";

const REGIONS = ["NTSC-U", "PAL", "NTSC-J", "Region-free"];
// mirrors the two book fields most shelves never change
const BOOK_FORMATS = ["Hardcover", "Paperback", "Trade Paperback", "Mass Market"];
const BOOK_JACKETS = ["With jacket", "No jacket"];

// What the stamp beside the title says while a section is open. Keyed by the
// same id the section is, so the two cannot drift apart.
const SECTION_LABEL = {
  name: "Collector name",
  collections: "Collections",
  display: "Display",
  profile: "Public profile",
  share: "Share",
  lock: "Lock",
  plan: "Plan",
  account: "Account",
  mine: "Your collection",
  sync: "Send it elsewhere",
  tokens: "Receive from elsewhere",
  backup: "Whole server",
};

/** One section of the settings accordion.
 *
 *  The head carries a summary of what is inside, so the page can be read
 *  without opening anything — "all 8 on", "2 shared", "off". Opening one
 *  closes the others, which is the whole reason a summary is needed: a
 *  stack of six shut drawers that said nothing would be worse than the
 *  scroll it replaced.
 *
 *  The body animates on grid-template-rows rather than height, so it does
 *  not need a measured pixel value and cannot disagree with its contents.
 */
function Section({ id, icon, name, summary, open, onToggle, children, stagger = true }) {
  return (
    <div className={`sec ${open === id ? "open" : ""}`} id={id}>
      <button
        className="sec-head"
        onClick={() => onToggle(open === id ? null : id)}
        aria-expanded={open === id}
      >
        <span className="sec-glyph">
          <Icon id={icon} />
        </span>
        <span className="sec-name">{name}</span>
        <span className="sec-sum">{summary}</span>
        <Icon id="chev" className="sec-chev" />
      </button>
      <div className="sec-body">
        <div className="sec-inner">
          <div className={`sec-pad ${stagger ? "stag" : ""}`}>{children}</div>
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { settings, save } = useSettings();
  // what this server carries, not what the code can draw
  const available = useAvailableModules();
  const profiles = usePublicProfiles();
  const hasModule = (key) => available.some((m) => m.key === key);
  const [name, setName] = useState("");
  const [saved, setSaved] = useState(false);
  const [version, setVersion] = useState("");
  // One at a time. Collections is open first because it is the section
  // people came here for — unless something sent us to a particular one,
  // which is what the hash is for: a binder's own settings link straight
  // through to the profile section, because deciding a binder is public
  // means nothing until the profile publishes cards at all.
  const { hash } = useLocation();
  const asked = hash.replace("#", "");
  const [open, setOpen] = useState(
    asked && SECTION_LABEL[asked] ? asked : "collections"
  );

  useEffect(() => {
    if (!asked || !SECTION_LABEL[asked]) return;
    setOpen(asked);
    // after the section has had a frame to open, so the scroll lands on it
    // rather than on where it used to be
    const t = setTimeout(() => {
      document.getElementById(asked)?.scrollIntoView({ block: "start" });
    }, 60);
    return () => clearTimeout(t);
  }, [asked]);

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
      <div className="set-head">
        <h2>Settings</h2>
        <span className="stamp">{saved ? "saved" : open ? SECTION_LABEL[open] : "all closed"}</span>
      </div>

      <div className="set-stack">
      <Section
        id="name"
        icon="user"
        name="Collector name"
        summary={name.trim() || "not set"}
        open={open}
        onToggle={setOpen}
      >
        <div className="set-field">
          <span className="set-label">Shown in the header</span>
          <input
            type="text"
            maxLength={50}
            placeholder="Leave blank for “Your Loot”"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => name !== (settings.owner_name || "") && flash({ owner_name: name.trim() })}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
        </div>
        <p className="sec-note">
          The header reads “{name.trim() || "Your"}’s Loot”.
          {profiles && " It is also the title of your public profile."}
        </p>
      </Section>

      <Section
        id="collections"
        icon="box"
        name="Collections"
        summary={
          enabled.length === available.length
            ? `all ${available.length} on`
            : `${enabled.length} of ${available.length} on`
        }
        open={open}
        onToggle={setOpen}
        stagger={false}
      >
        <p className="sec-note">
          Turn off what you don't collect and it goes — nothing is deleted.
          Items stay in the database and stop appearing anywhere; turning it
          back on returns everything exactly as it was.
        </p>
        <div className="optrows stag">
          {available.map((m) => {
            const on = enabled.includes(m.key);
            return (
              <div key={m.key} className={`optrow ${on ? "on" : ""}`}>
                <Icon id={m.icon} />
                <span className="opttext">
                  <strong>{m.label}</strong>
                  <small>{m.blurb}</small>
                </span>
                <button
                  className="sw"
                  role="switch"
                  aria-checked={on}
                  title={m.label}
                  onClick={() => toggleModule(m.key)}
                />
              </div>
            );
          })}
        </div>
      </Section>

      {/* Every row here is a default for one collection, so each is drawn
          only where this server carries it — a "default region for games"
          on an install with no games configures nothing. The Pokédex toggle
          that used to live here is gone: the card list has its own, in the
          row above the cards it affects, which is where you actually reach
          for it. Two switches for one setting is one too many. */}
      {(hasModule("books") || hasModule("games") || hasModule("hardware")) && (
      <Section
        id="display"
        icon="sliders"
        name="Display"
        summary={[
          hasModule("books") && settings.default_book_format,
          (hasModule("games") || hasModule("hardware")) && settings.default_region,
        ].filter(Boolean).join(" · ")}
        open={open}
        onToggle={setOpen}
      >
        {hasModule("books") && (
          <div className="set-field">
            <span className="set-label">Books are usually</span>
            <div className="duo">
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
          </div>
        )}
        {(hasModule("games") || hasModule("hardware")) && (
          <div className="set-field">
            <span className="set-label">
              Default region — games &amp; hardware
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
        <p className="sec-note">
          Defaults only. Any item can be changed when you add it.
        </p>
      </Section>
      )}

      {/* One or the other, never both — see usePublicProfiles. */}
      {profiles ? (
        <ProfileCard open={open} onToggle={setOpen} />
      ) : (
        <ShareCard enabled={enabled} open={open} onToggle={setOpen} />
      )}
      <LockCard open={open} onToggle={setOpen} />
      <PlanCard open={open} onToggle={setOpen} />
      <AccountCard open={open} onToggle={setOpen} />
      <MyBackupCard open={open} onToggle={setOpen} />
      <SyncCard open={open} onToggle={setOpen} />
      <TokensCard open={open} onToggle={setOpen} />
      <BackupCard open={open} onToggle={setOpen} />
      </div>

      <DataSources />
      <PolicyLinks />
      {version && <p className="version-tag">Your Loot v{version}</p>}
    </div>
  );
}

const TOTAL = (r) => Object.values(r || {}).reduce((a, b) => a + b, 0);

const SIZE = (b) =>
  b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`;

/** The public profile: a name chosen once, and shelves you opt in to.
 *
 *  Two decisions that look similar and are not. Which collections are public
 *  can be changed whenever, because it only affects what a page shows today.
 *  The name cannot be changed at all — it is the address, and an address that
 *  moves breaks every link anybody wrote down. So the form says so before it
 *  is used rather than explaining it afterwards.
 *
 *  Absent entirely on an install with no profiles: the endpoint answers, but
 *  a home server that nobody can reach has nothing to publish to.
 */
function ProfileCard({ open, onToggle }) {
  const [me, setMe] = useState(null);
  const [wanted, setWanted] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.profile().then(setMe).catch(() => {});
  }, []);
  if (!me) return null;

  const origin = window.location.origin;

  const claim = async () => {
    if (!wanted.trim()) return;
    setBusy(true);
    setProblem(null);
    try {
      setMe(await api.saveProfile({ screen_name: wanted.trim() }));
      setWanted("");
    } catch (e) {
      setProblem(e.message);
    } finally {
      setBusy(false);
    }
  };

  const setLoose = async (on) => {
    setMe({ ...me, loose: on });          // the switch should move at once
    setProblem(null);
    try {
      setMe(await api.saveProfile({ loose: on }));
    } catch (e) {
      setProblem(e.message);
      api.profile().then(setMe).catch(() => {});
    }
  };

  const toggle = async (scope) => {
    const next = me.collections.includes(scope)
      ? me.collections.filter((s) => s !== scope)
      : [...me.collections, scope];
    setMe({ ...me, collections: next }); // the tick should land immediately
    try {
      setMe(await api.saveProfile({ collections: next }));
    } catch (e) {
      setProblem(e.message);
      api.profile().then(setMe).catch(() => {});
    }
  };

  return (
    <Section

      id="profile"

      icon="globe"

      name="Public profile"

      summary={
          me.can_claim
            ? "no name yet"
            : me.collections.length
              ? `${me.collections.length} shared`
              : "private"
        }

      open={open}

      onToggle={onToggle}

    >

      {me.can_claim && !me.fixed_url ? (
        <>
          <p>
            A page you can send anybody, showing only the collections you pick
            below. It needs a name, and that name{" "}
            <strong>cannot be changed later</strong> — it is the address, and
            an address that moves breaks every link you have given out. Choose
            it as carefully as you would a username anywhere else.
          </p>
          {me.name_revoked && (
            <p className="error">
              <Icon id="alert" />
              Your previous name was removed by an administrator. You can
              choose one more.
            </p>
          )}
          <div className="form-row">
            <span className="game-info-line">{origin}/u/</span>
            <input
              type="text"
              className="grow"
              maxLength={30}
              placeholder="yourname"
              value={wanted}
              onChange={(e) => setWanted(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), claim())}
            />
            <button
              type="button"
              className="primary"
              disabled={busy || wanted.trim().length < 3}
              onClick={claim}
            >
              {busy ? "…" : "Claim it"}
            </button>
          </div>
          {problem && <p className="error">{problem}</p>}
        </>
      ) : (
        <>
          {me.fixed_url && (
            <p>
              A page you can send anybody, showing only the collections you
              pick below. On your own server it lives at a fixed address — no
              name to claim — and the user guide covers how to put just this
              page on the internet without exposing the rest of your machine.
            </p>
          )}
          {/* The address, and a way to take it somewhere. Copying is what
              people actually do with this — the whole point of the page is
              being pasted into a chat. */}
          <div className="urlrow">
            <a className="url" href={me.url} target="_blank" rel="noopener noreferrer">
              {origin.replace(/^https?:\/\//, "")}
              <em>{me.url}</em>
            </a>
            <button
              type="button"
              className="ghost icon"
              title={copied === "main" ? "Copied" : "Copy link"}
              onClick={() => {
                navigator.clipboard?.writeText(origin + me.url).then(
                  () => {
                    setCopied("main");
                    setTimeout(() => setCopied(false), 1400);
                  },
                  () => setProblem("Could not copy — select the link instead."),
                );
              }}
            >
              <Icon id={copied === "main" ? "check" : "copy"} />
            </button>
          </div>
          {problem && <p className="error">{problem}</p>}
        </>
      )}

      <div className="set-field">
        <span className="set-label">Show publicly</span>
        <div className="shelf">
          {me.available.map((a) => (
            <button
              key={a.scope}
              type="button"
              className={`chip ${me.collections.includes(a.scope) ? "active" : ""}`}
              disabled={me.can_claim}
              title={me.can_claim ? "Claim a name first" : ""}
              onClick={() => toggle(a.scope)}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
      {me.collections.includes("cards") && (
        <div className="optrows">
          {/* The same row the module switches use — an icon, the text, the
              switch — because it is the same kind of decision and a second
              layout for it is a second thing to keep in step. */}
          <div className={`optrow ${me.loose ? "on" : ""}`}>
            <Icon id="card" />
            <span className="opttext">
              <strong>Loose cards</strong>
              <small>
                Cards that are not in any binder, in a box beside the shelf.
                Off, only your binders are shown.
              </small>
            </span>
            <button
              className="sw"
              role="switch"
              aria-checked={!!me.loose}
              title="Loose cards"
              disabled={me.can_claim}
              onClick={() => setLoose(!me.loose)}
            />
          </div>
        </div>
      )}
      {/* One address per shelf. Most people keep one collection, and the
          link they want to hand somebody is the link to that — not to
          everything they own with the interesting part three scrolls down.
          The server decides which of these exist, so a link is never
          offered that would answer "not found". */}
      {me.links?.length > 0 && (
        <div className="set-field">
          <span className="set-label">Straight to one shelf</span>
          <div className="focuslinks">
            {me.links.map((l) => (
              <div className="urlrow" key={l.path}>
                <a className="url" href={l.path} target="_blank" rel="noopener noreferrer">
                  {l.label}
                  <em>{l.path}</em>
                </a>
                <button
                  type="button"
                  className="ghost icon"
                  title={copied === l.path ? "Copied" : "Copy link"}
                  onClick={() => {
                    navigator.clipboard?.writeText(origin + l.path).then(
                      () => {
                        setCopied(l.path);
                        setTimeout(() => setCopied(false), 1400);
                      },
                      () => setProblem("Could not copy — select the link instead."),
                    );
                  }}
                >
                  <Icon id={copied === l.path ? "check" : "copy"} />
                </button>
              </div>
            ))}
          </div>
          <p className="sec-note">
            Each one opens your page with that collection already showing.
          </p>
        </div>
      )}
      <p className="sec-note">
        Anybody with the link can see it and search engines can find it.
        Nothing is public until you tick it. Notes, tags, serial and
        certificate numbers are never included, whatever you choose.
        {!me.can_claim && !me.fixed_url &&
          " The name is fixed — contact support if there is a problem with it."}
      </p>
      {!me.can_claim && me.collections.length === 0 && (
        <p className="sec-note">
          Nothing ticked, so the page does not answer at all — the link returns
          “not found” rather than an empty shelf.
        </p>
      )}
    </Section>
  );
}

/** Sharing is an export, not a link.
 *
 *  A link would need this server to be reachable from wherever the other
 *  person is, and most of these installs sit on a home network behind a
 *  router that has never been asked to forward anything. A file is sent the
 *  same way as any other file, works offline, and stops existing when they
 *  delete it — no public URL left listening after you have forgotten about
 *  it.
 */
function ShareCard({ enabled, open, onToggle }) {
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
    <Section

      id="share"

      icon="down"

      name="Share a collection"

      summary={"a file you send"}

      open={open}

      onToggle={onToggle}

    >
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
    </Section>
  );
}

/** Radarr and Sonarr put this in settings rather than in a config file, and
 *  they're right to: turning the lock on is a decision you make once you've
 *  already got the app open, not something you want to restart a container
 *  for. */
function LockCard({ open, onToggle }) {
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
    <Section

      id="lock"

      icon="lock"

      name="Lock this app"

      summary={me.locked ? "on" : "off"}

      open={open}

      onToggle={onToggle}

    >
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
    </Section>
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
function PlanCard({ open, onToggle }) {
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

  // On the tier, however they got there — bought, granted, or never billed
  // because they run the place. The plan string alone answered "which one did
  // you buy", which is a different question and read as Free to an admin.
  const onTier = state.subscribed;
  const names = paidModules.map((m) => m.label).join(", ");

  return (
    <Section

      id="plan"

      icon="coin"

      name="Your plan"

      summary={state.subscribed ? "Supporter" : "Free"}

      open={open}

      onToggle={onToggle}

    >
      {onTier ? (
        <>
          <p>
            You're on <strong>Supporter</strong>
            {state.never_billed
              ? " — you run this server, so you are never billed for it."
              : state.plan_until
                ? ` — paid until ${new Date(state.plan_until).toLocaleDateString()}.`
                : "."}{" "}
            {state.never_billed ? "" : "Thank you, genuinely."}
          </p>
          {state.can_manage && !state.never_billed && (
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
    </Section>
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

/** Where the data comes from, said once, on every install.
 *
 *  Every catalogue this app searches belongs to somebody else, and several of
 *  them require credit as a condition of use — Discogs' wording is theirs
 *  verbatim, required by their API terms on any application, personal or
 *  commercial. The rest are thanked because they have earned it.
 */
function DataSources() {
  return (
    <section className="settings-card">
      <h3>Where the data comes from</h3>
      <p className="settings-note" style={{ display: "flex", flexWrap: "wrap", gap: "8px 16px" }}>
        <a href="https://www.igdb.com" target="_blank" rel="noopener noreferrer">IGDB.com</a>
        <a href="https://www.discogs.com" target="_blank" rel="noopener">Discogs</a>
        <a href="https://musicbrainz.org" target="_blank" rel="noopener noreferrer">MusicBrainz</a>
        <a href="https://openlibrary.org" target="_blank" rel="noopener noreferrer">Open Library</a>
        <a href="https://rebrickable.com" target="_blank" rel="noopener noreferrer">Rebrickable</a>
        <a href="https://tcgdex.dev" target="_blank" rel="noopener noreferrer">TCGdex</a>
      </p>
      <p className="settings-note">
        Games data by IGDB.com. Records search data provided by Discogs — this
        application uses Discogs&rsquo; API but is not affiliated with,
        sponsored or endorsed by Discogs. &lsquo;Discogs&rsquo; is a trademark
        of Zink Media, LLC.
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
function AccountCard({ open, onToggle }) {
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
    <Section

      id="account"

      icon="user"

      name="Your account"

      summary={me?.user?.email || ""}

      open={open}

      onToggle={onToggle}

    >
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
    </Section>
  );
}

/** Your collection, out and back in.
 *
 *  Everybody's, on every plan, on the day a plan lapses — a collection you
 *  cannot get out of is a hostage, and this is where that promise is kept.
 *  The card above it belongs to whoever runs the server and holds everybody's
 *  rows; this one holds only yours and can only ever write yours back.
 *
 *  The confirmation is typed rather than clicked because a restore clears
 *  what is in the account first. A dialog people have learned to dismiss is
 *  not a decision.
 */
function MyBackupCard({ open, onToggle }) {
  const fileInput = useRef(null);
  const [chosen, setChosen] = useState(null);
  const [word, setWord] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const pick = (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // so the same file can be picked again after an error
    setError(null);
    setResult(null);
    setWord("");
    if (file) setChosen(file);
  };

  const go = async () => {
    if (!chosen) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.restoreMine(chosen, word.trim());
      setResult(r);
      setChosen(null);
      setWord("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section
      id="mine"
      icon="save"
      name="Your collection"
      summary={"a copy you keep"}
      open={open}
      onToggle={onToggle}
    >
      <p>
        A file holding everything of yours — every item, every copy with its
        condition and notes, your wanted list, your binders and the photographs
        you uploaded. It restores into your account on any Your Loot, and
        nothing on this page is ever behind a plan.
      </p>
      <div className="form-row wrap">
        <a className="primary" href={api.myBackupUrl} download>
          <Icon id="save" />
          Back up my collection
        </a>
        <button
          className="ghost"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          <Icon id="upload" />
          Restore my collection…
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".zip,application/zip"
          style={{ display: "none" }}
          onChange={pick}
        />
      </div>

      {chosen && (
        <div className="confirm-box">
          <p>
            <strong>{chosen.name}</strong> will replace what is in your account.
            Your copies, wanted list, binders and tags are cleared and rebuilt
            from the file. Nobody else's collection is touched, on this server
            or any other.
          </p>
          <label className="set-field">
            <span className="set-label">Type RESTORE to confirm</span>
            <input
              value={word}
              onChange={(e) => setWord(e.target.value)}
              placeholder="RESTORE"
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck="false"
            />
          </label>
          <div className="form-row wrap">
            <button
              className="primary danger"
              disabled={busy || word.trim().toUpperCase() !== "RESTORE"}
              onClick={go}
            >
              {busy ? "Restoring…" : "Replace my collection"}
            </button>
            <button className="ghost" disabled={busy} onClick={() => setChosen(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

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
            {result.items.toLocaleString()} items and {result.copies.toLocaleString()} copies
            {result.images ? `, ${result.images} photographs` : ""}
          </strong>
          <small>
            {result.binders} binders, {result.tags} tags
            {result.skipped
              ? ` · ${result.skipped} left out — this server does not carry that collection`
              : ""}
            {result.created_at ? ` · from a copy taken ${result.created_at.replace("T", " ")}` : ""}
          </small>
          <button className="primary" onClick={() => window.location.reload()}>
            Reload to see it
          </button>
        </div>
      )}
    </Section>
  );
}

function BackupCard({ open, onToggle }) {
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
    <Section

      id="backup"

      icon="box"

      name="Backup & restore"

      summary={""}

      open={open}

      onToggle={onToggle}

    >
      <p>
        A zip holding the whole server — every account, everything they own,
        and the uploaded photographs. Keep one somewhere that isn't this
        machine.
      </p>
      <p className="settings-note">
        It restores <strong>only into an install with nothing in it</strong> —
        a rebuilt machine or a fresh database. A server with collections on it
        refuses, because a restore here would replace all of them. To bring a
        collection into this one, use Your collection above.
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
    </Section>
  );
}

/** "2 hours ago", for a timestamp the server wrote. */
function since(iso) {
  if (!iso) return null;
  const t = Date.parse(iso.endsWith("Z") ? iso : iso + "Z");
  if (Number.isNaN(t)) return null;
  const m = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (m < 2) return "just now";
  if (m < 90) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 36) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.round(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}

/** Send this collection to another Your Loot — the hosted one, usually — so
 *  the public page there stays current while this server stays private.
 *
 *  The other account becomes a mirror: replaced wholesale on every send, so
 *  anything edited there is overwritten by the next one. Said here rather
 *  than discovered, because "my card vanished from the app" would otherwise
 *  be the way people learn it. */
function SyncCard({ open, onToggle }) {
  const [st, setSt] = useState(null);
  const [url, setUrl] = useState("https://yourloot.app");
  const [token, setToken] = useState("");
  const [nightly, setNightly] = useState(false);
  const [onChange, setOnChange] = useState(false);
  const [busy, setBusy] = useState(null); // "save" | "now" | "forget"
  const [error, setError] = useState(null);
  const [flash, setFlash] = useState(null);

  const load = () =>
    api.sync().then((r) => {
      setSt(r);
      if (r.url) setUrl(r.url);
      setNightly(!!r.nightly);
      setOnChange(!!r.on_change);
    }).catch(() => {});
  useEffect(() => { load(); }, []);

  const run = async (what, fn) => {
    setBusy(what); setError(null); setFlash(null);
    try {
      const r = await fn();
      if (r && r.configured !== undefined) setSt(r);
      setToken("");
      if (what === "now") setFlash("Sent.");
      if (what === "save") setFlash("Saved.");
      if (what === "forget") { setSt({ configured: false }); setUrl("https://yourloot.app"); setNightly(false); setOnChange(false); }
    } catch (e) {
      setError(e.message);
      load();
    } finally {
      setBusy(null);
    }
  };

  const summary = !st ? "…"
    : !st.configured ? "off"
    : st.last_error ? "last send failed"
    : st.pending ? "changes waiting"
    : st.last_at ? `sent ${since(st.last_at)}` : "ready";
  const res = st?.last_result;

  return (
    <Section id="sync" icon="cloud" name="Send it elsewhere" summary={summary} open={open} onToggle={onToggle}>
      <p>
        Send this collection to an account on another Your Loot — the hosted
        one at yourloot.app, usually — so the public page there is always
        current, without this server being reachable from anywhere. Nothing
        comes in; this server pushes out.
      </p>
      <p className="settings-note">
        That account becomes a <strong>mirror</strong>: everything in it is
        replaced by what is here, every time. Keep your collection <em>here</em>,
        and treat what is there as a copy. Which shelves are public is still
        decided over there, in that account's settings.
      </p>
      <p className="settings-note">
        On the other account: <strong>Settings → Receive from elsewhere →
        Create a sync token</strong>, and paste it below. That token can do one
        thing — receive a collection — and nothing else.
      </p>
      <div className="set-fields">
        <label className="set-field">
          Address of the other Your Loot
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://yourloot.app" autoComplete="off" />
        </label>
        <label className="set-field">
          Sync token {st?.configured && st.token_prefix ? <span className="settings-note">(saved · {st.token_prefix}…)</span> : null}
          <input type="password" value={token} onChange={(e) => setToken(e.target.value)}
                 placeholder={st?.configured ? "leave blank to keep the saved one" : "paste it here"} autoComplete="off" />
        </label>
        <label className="check">
          <input type="checkbox" checked={nightly} onChange={(e) => setNightly(e.target.checked)} />
          Send it every night
        </label>
        <label className="check">
          <input type="checkbox" checked={onChange} onChange={(e) => setOnChange(e.target.checked)} />
          Send it a few minutes after I change something
        </label>
      </div>
      <div className="form-row wrap">
        <button className="primary" disabled={busy !== null || !url.trim() || (!token.trim() && !st?.configured)}
                onClick={() => run("save", () => api.saveSync({ url: url.trim(), token: token.trim() || null, nightly, on_change: onChange }))}>
          {busy === "save" ? "…" : "Save"}
        </button>
        <button className="ghost" disabled={busy !== null || !st?.configured}
                onClick={() => run("now", () => api.syncNow())}>
          <Icon id="upload" />
          {busy === "now" ? "Sending…" : "Send now"}
        </button>
        {st?.configured && (
          <button className="ghost" disabled={busy !== null}
                  onClick={() => run("forget", () => api.forgetSync())}
                  title="Stop sending, and forget the token. The mirror keeps what it was last sent.">
            <Icon id="x" />
            Stop
          </button>
        )}
      </div>
      {flash && <p className="settings-note">{flash}</p>}
      {error && <p className="error"><Icon id="alert" />{error}</p>}
      {st?.last_error && !error && (
        <p className="error"><Icon id="alert" />Last send failed: {st.last_error}</p>
      )}
      {st?.pending && !busy && (
        <p className="settings-note">Changes waiting — they go a few minutes after the last one.</p>
      )}
      {st?.last_at && res && (
        <p className="settings-note">
          Last sent {since(st.last_at)} — {res.copies} {res.copies === 1 ? "copy" : "copies"},{" "}
          {res.wanted} wanted, {res.binders} {res.binders === 1 ? "binder" : "binders"}
          {res.images ? `, ${res.images} new photo${res.images === 1 ? "" : "s"}` : ""}
          {res.skipped ? ` · ${res.skipped} item${res.skipped === 1 ? "" : "s"} skipped (collections that server doesn't carry)` : ""}
        </p>
      )}
    </Section>
  );
}

/** The other half: let another Your Loot send its collection into *this*
 *  account. The token it needs is minted here, shown once, and can only do
 *  that one thing. */
function TokensCard({ open, onToggle }) {
  const { settings } = useSettings();
  const mirror = settings?.mirror;
  const [stopping, setStopping] = useState(false);
  const stop = async () => {
    setStopping(true);
    try {
      await api.stopMirroring();
      // the bar on every page reads the settings the app loaded; the simplest
      // honest way to make it go is to load them again
      window.location.reload();
    } catch (e) {
      setError(e.message);
      setStopping(false);
    }
  };
  const [rows, setRows] = useState(null);
  const [name, setName] = useState("my home server");
  const [fresh, setFresh] = useState(null); // the one-time value
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = () => api.tokens().then((r) => setRows(r.tokens || [])).catch(() => setRows([]));
  useEffect(() => { load(); }, []);

  const make = async () => {
    setBusy(true); setError(null);
    try {
      const r = await api.createToken(name.trim() || "sync", "sync");
      setFresh(r);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const revoke = async (id) => {
    setError(null);
    try { await api.revokeToken(id); load(); } catch (e) { setError(e.message); }
  };

  const live = (rows || []).filter((t) => !t.revoked_at && t.scope === "sync");
  const summary = mirror ? `mirror of ${mirror.source}`
    : rows === null ? "…" : live.length ? `${live.length} token${live.length === 1 ? "" : "s"}` : "none";

  return (
    <Section id="tokens" icon="lock" name="Receive from elsewhere" summary={summary} open={open} onToggle={onToggle}>
      <p>
        Let a Your Loot you run at home send its collection into this account,
        so this account mirrors it. Make a token here, paste it into{" "}
        <strong>Settings → Send it elsewhere</strong> on that server, and this
        account is replaced with that collection on every send.
      </p>
      <p className="settings-note">
        A sync token can do exactly one thing: receive a collection. It cannot
        read anything, change the account, or make more tokens. Revoke it here
        and the next send is refused.
      </p>
      {mirror && (
        <div className="mirror-note">
          <p>
            <strong>This account is a mirror of {mirror.source}</strong>
            {mirror.at ? ` — last received ${since(mirror.at)}.` : "."} Everything
            here is replaced on every send; make changes there, not here. Which
            shelves are public is the one thing that is yours to decide here.
          </p>
          <button className="ghost" disabled={stopping} onClick={stop}
                  title="Stop being a mirror: the bar goes and every sync token here is revoked">
            <Icon id="x" />
            {stopping ? "…" : "Stop mirroring"}
          </button>
        </div>
      )}
      <div className="form-row wrap">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="what it's for" maxLength={60} />
        <button className="primary" disabled={busy} onClick={make}>
          <Icon id="plus" />
          {busy ? "…" : "Create a sync token"}
        </button>
      </div>
      {fresh && (
        <div className="token-once">
          <p className="settings-note">
            Copy this now — it is shown once and cannot be shown again.
          </p>
          <code>{fresh.token}</code>
          <button className="ghost" onClick={() => setFresh(null)}>Done</button>
        </div>
      )}
      {error && <p className="error"><Icon id="alert" />{error}</p>}
      {live.length > 0 && (
        <ul className="token-list">
          {live.map((t) => (
            <li key={t.id}>
              <span className="tok-name">{t.name}</span>
              <span className="tok-prefix">{t.prefix}…</span>
              <span className="settings-note">
                {t.last_used_at ? `used ${since(t.last_used_at)}` : "never used"}
              </span>
              <button className="ghost" onClick={() => revoke(t.id)} title="Revoke — the next send with it is refused">
                <Icon id="trash" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
