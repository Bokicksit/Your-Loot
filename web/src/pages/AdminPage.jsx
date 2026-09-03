import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

/** The operator's page: who is here, who has paid, what the server holds.
 *
 *  Nothing per-person beyond what running a service requires — no last-seen,
 *  no activity, no counting how often somebody opens the app. The people
 *  here handed over a list of everything they own; the least they are owed is
 *  that nobody is watching them use it.
 */

const fmtBytes = (n) => {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`;
};

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString() : "—");

function Stat({ label, value, note }) {
  return (
    <div className="admin-stat">
      <span className="admin-stat-label">{label}</span>
      <span className="admin-stat-value">{value}</span>
      {note && <span className="admin-stat-note">{note}</span>}
    </div>
  );
}

/** Names set aside before anybody claims them.
 *
 *  A screen name is claimed once and never changed, so the moment of
 *  claiming is the only one that matters — this gets ahead of it. Reserve
 *  "ben" today; assign it to the kid's email whenever he finally has one,
 *  and his claim goes through where everybody else's bounces.
 */
function ReservedNames() {
  const [rows, setRows] = useState(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [drafts, setDrafts] = useState({}); // id -> email being retyped
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = () =>
    api.reservedNames().then((r) => {
      setRows(r);
      setDrafts({});
    });

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, []);

  const reserve = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy("new");
    setErr(null);
    try {
      await api.reserveName(name.trim(), email.trim() || null);
      setName("");
      setEmail("");
      await load();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(null);
    }
  };

  const assign = async (r) => {
    setBusy(r.id);
    setErr(null);
    try {
      await api.assignReservation(r.id, (drafts[r.id] ?? "").trim() || null);
      await load();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(null);
    }
  };

  const release = async (r) => {
    if (
      !window.confirm(
        `Release “${r.display}”?\n\nThe name goes back in circulation — the next person to want it gets it.`,
      )
    )
      return;
    setBusy(r.id);
    setErr(null);
    try {
      await api.releaseReservation(r.id);
      await load();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(null);
    }
  };

  if (rows === null && !err) return null;

  return (
    <section className="settings-card">
      <h3>Reserved names</h3>
      {err && (
        <p className="settings-note" style={{ color: "var(--danger, #ff8080)" }}>{err}</p>
      )}
      <form className="form-row wrap" onSubmit={reserve}>
        <input
          type="text"
          placeholder="Name to hold (ben)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ maxWidth: 200 }}
        />
        <input
          type="email"
          className="grow"
          placeholder="Email allowed to claim it (optional)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button type="submit" className="ghost" disabled={busy === "new" || !name.trim()}>
          {busy === "new" ? "…" : "Reserve"}
        </button>
      </form>
      {rows && rows.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <tbody>
              <tr>
                <th>Name</th>
                <th>Who may claim it</th>
                <th />
              </tr>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <span className="admin-who">/u/{r.name}</span>
                  </td>
                  <td>
                    <input
                      type="email"
                      placeholder="Nobody yet — add an email"
                      value={drafts[r.id] ?? r.email ?? ""}
                      onChange={(e) =>
                        setDrafts((d) => ({ ...d, [r.id]: e.target.value }))
                      }
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), assign(r))}
                      style={{ width: "100%", maxWidth: 320 }}
                    />
                  </td>
                  <td className="admin-acts">
                    {drafts[r.id] !== undefined &&
                      (drafts[r.id] ?? "") !== (r.email ?? "") && (
                        <button
                          type="button"
                          className="ghost"
                          disabled={busy === r.id}
                          onClick={() => assign(r)}
                        >
                          {busy === r.id ? "…" : "Save"}
                        </button>
                      )}
                    <button
                      type="button"
                      className="ghost danger"
                      disabled={busy === r.id}
                      title="Put the name back in circulation"
                      onClick={() => release(r)}
                    >
                      Release
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="settings-note">
        A reserved name can't be claimed by anyone — except the account with
        the email you put on it, whose claim goes through and uses the
        reservation up. That works at sign-up too: if they type the held name
        it's theirs, and if they type a different one they're stopped and
        told a name is waiting, so they can't accidentally spend their
        once-ever claim on something else. Reserving can't take a name
        somebody already holds; that's what Remove name above is for, and it
        spends the name for everybody.
      </p>
    </section>
  );
}

/** One card of one set, compact enough that a 250-card set stays a page. */
function ArtTile({ card, selected, onSelect }) {
  return (
    <button
      type="button"
      className={`art-tile ${card.image_url ? "" : "artless"} ${selected ? "on" : ""}`}
      onClick={onSelect}
      title={card.image_url ? "Change this picture" : "No picture — add one"}
    >
      {card.image_url ? (
        <img src={card.image_url} data-item={card.id} alt="" loading="lazy" />
      ) : (
        <span className="art-hole">no art</span>
      )}
      <span className="art-name">{card.title}</span>
      <span className="art-no">{card.card_number}</span>
    </button>
  );
}

/** Curating the catalogue's card art.
 *
 *  The dump ships some cards without a picture and some with the wrong one.
 *  This is where the operator fixes that — and because the catalogue is
 *  shared, a picture fixed here is fixed for every collection on the server
 *  at once. English sets only: this screen is for art a person can check
 *  against a card, and the Japanese catalogue is better served by a reseed.
 */
function CardArt() {
  const [sets, setSets] = useState(null);
  const [openSet, setOpenSet] = useState(null);   // set_code of the open panel
  const [cards, setCards] = useState({});          // set_code -> [card]
  const [picked, setPicked] = useState(null);      // the card being edited
  const [link, setLink] = useState("");
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [hash, setHash] = useState(null);          // {pending, running}

  const loadSets = () => api.adminCardSets().then(setSets);
  const loadHash = () => api.adminHashArtStatus().then(setHash);

  useEffect(() => {
    loadSets().catch((e) => setErr(e.message));
    loadHash().catch(() => {});
  }, []);

  // While a fingerprint pass runs, watch it: the button reads better
  // counting down than saying "pressed".
  useEffect(() => {
    if (!hash?.running) return;
    const t = setInterval(() => loadHash().catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [hash?.running]);

  const expand = async (code) => {
    const next = openSet === code ? null : code;
    setOpenSet(next);
    setPicked(null);
    setLink("");
    if (next && !cards[next]) {
      try {
        const rows = await api.adminSetCards(next);
        setCards((c) => ({ ...c, [next]: rows }));
      } catch (e) {
        setErr(e.message);
      }
    }
  };

  /** The new picture is on our server; put it on the card, for everybody.
   *  The PATCH also clears the card's fingerprint, so the next pass —
   *  or the button below — teaches the scanner the new face. */
  const apply = async (localUrl) => {
    await api.updateCard(picked.id, { image_url: localUrl });
    setCards((c) => ({
      ...c,
      [openSet]: c[openSet].map((k) =>
        k.id === picked.id ? { ...k, image_url: localUrl, hashed: false } : k
      ),
    }));
    setPicked(null);
    setLink("");
    loadSets().catch(() => {});
    loadHash().catch(() => {});
  };

  const pullLink = async () => {
    if (!link.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      // copied onto our own disk first: a hotlink dies when the source
      // moves, and this picture is about to be everybody's
      const { url } = await api.fetchImage(link.trim());
      await apply(url);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const uploadFile = async (file) => {
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      const { url } = await api.uploadImage(file);
      await apply(url);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const fingerprint = async () => {
    setErr(null);
    try {
      const r = await api.adminHashArt();
      setHash({ pending: r.pending, running: r.started || r.running });
    } catch (e) {
      setErr(e.message);
    }
  };

  if (sets === null && !err) return null;

  const shown = (openSet && cards[openSet]) || [];
  const visible = onlyMissing ? shown.filter((c) => !c.image_url) : shown;

  return (
    <section className="settings-card">
      <h3>Card art</h3>
      <p className="settings-note">
        The catalogue's own pictures — fix one here and it is fixed for every
        collection on this server. Pick a card, then hand it a link or a file.
      </p>
      {err && (
        <p className="settings-note" style={{ color: "var(--danger, #ff8080)" }}>{err}</p>
      )}

      <div className="form-row wrap">
        <button
          type="button"
          className="ghost"
          disabled={hash?.running || !hash?.pending}
          onClick={fingerprint}
          title="Teach the scanner the pictures it does not know yet"
        >
          {hash?.running
            ? `Fingerprinting… ${hash.pending} to go`
            : hash?.pending
              ? `Create fingerprints (${hash.pending} waiting)`
              : "Scanner is up to date"}
        </button>
        <label className="admin-friend" title="Hide the cards that already have art">
          <input
            type="checkbox"
            checked={onlyMissing}
            onChange={(e) => setOnlyMissing(e.target.checked)}
          />
          only missing
        </label>
      </div>

      <div className="admin-sets">
        {sets?.map((s) => (
          <div key={s.set_code} className="admin-set">
            <button
              type="button"
              className={`admin-set-head ${openSet === s.set_code ? "open" : ""}`}
              onClick={() => expand(s.set_code)}
              aria-expanded={openSet === s.set_code}
            >
              <Icon id="chev" className={openSet === s.set_code ? "turned" : ""} />
              <strong>{s.set_name || s.set_code}</strong>
              {s.set_abbr && <span className="admin-name">{s.set_abbr}</span>}
              {s.set_year && <span className="admin-name">{s.set_year}</span>}
              <span className="sp" />
              <span className="admin-name">{s.total} cards</span>
              {s.missing > 0 && (
                <span className="admin-flag">{s.missing} without art</span>
              )}
            </button>

            {openSet === s.set_code && (
              <div className="admin-set-body">
                {picked && (
                  <div className="art-editor">
                    {picked.image_url ? (
                      <img src={picked.image_url} data-item={picked.id} alt="" />
                    ) : (
                      <span className="art-hole">no art</span>
                    )}
                    <div className="art-editor-fields">
                      <strong>
                        {picked.title}
                        {picked.card_number && <small> · {picked.card_number}</small>}
                      </strong>
                      <div className="form-row">
                        <input
                          type="url"
                          className="grow"
                          placeholder="Paste an image link — it is copied to this server"
                          value={link}
                          onChange={(e) => setLink(e.target.value)}
                          onKeyDown={(e) =>
                            e.key === "Enter" && (e.preventDefault(), pullLink())
                          }
                        />
                        <button
                          type="button"
                          className="ghost"
                          disabled={busy || !link.trim()}
                          onClick={pullLink}
                        >
                          {busy ? "…" : "Pull from link"}
                        </button>
                        <label className={`ghost btnish ${busy ? "off" : ""}`}>
                          <Icon id="upload" />
                          Upload
                          <input
                            type="file"
                            accept="image/*"
                            hidden
                            disabled={busy}
                            onChange={(e) => uploadFile(e.target.files?.[0])}
                          />
                        </label>
                        <button
                          type="button"
                          className="ghost icon"
                          title="Close"
                          onClick={() => {
                            setPicked(null);
                            setLink("");
                          }}
                        >
                          <Icon id="x" />
                        </button>
                      </div>
                    </div>
                  </div>
                )}
                {!cards[s.set_code] ? (
                  <p className="settings-note">Loading…</p>
                ) : visible.length === 0 ? (
                  <p className="settings-note">
                    {onlyMissing ? "Every card here has a picture." : "No cards."}
                  </p>
                ) : (
                  <div className="art-grid">
                    {visible.map((c) => (
                      <ArtTile
                        key={c.id}
                        card={c}
                        selected={picked?.id === c.id}
                        onSelect={() => {
                          setPicked(c);
                          setLink("");
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="settings-note">
        A changed picture clears that card's fingerprint, so the scanner
        forgets the old face — press the button above (or let the
        HASH_CARD_ART pass on restart do it) and it learns the new one.
      </p>
    </section>
  );
}

export default function AdminPage() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = () =>
    Promise.all([api.adminStats(), api.adminUsers()])
      .then(([s, u]) => {
        setStats(s);
        setUsers(u);
        setError(null);
      })
      .catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  /** Take somebody's screen name away.
   *
   *  The only lever there is, and deliberately the only one: it removes a
   *  name but cannot choose a replacement. Picking names for people would
   *  make you responsible for the next one.
   *
   *  Confirmed because it cannot be undone — the name is spent afterwards,
   *  for them and for everybody else, which is the point of it.
   */
  const revokeName = async (u) => {
    if (
      !window.confirm(
        `Remove the name “${u.screen_name}”?

` +
          "Their profile stops answering and nobody can ever claim that name " +
          "again, including them. They may choose one different name. " +
          "Their collection is untouched.",
      )
    )
      return;
    setBusy(u.id);
    setError(null);
    try {
      await api.revokeScreenName(u.id);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  /** A plan given rather than sold. Only the arithmetic changes — what they
   *  can open is decided by the plan, which is real either way. */
  const setComped = async (id, comped) => {
    setBusy(id);
    setError(null);
    try {
      await api.adminSetComped(id, comped);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const setPlan = async (id, plan) => {
    setBusy(id);
    setError(null);
    try {
      await api.adminSetPlan(id, { plan, until: null });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  if (error && !stats) {
    return (
      <div className="empty">
        <span className="glyph"><Icon id="alert" /></span>
        <strong>Not available</strong>
        <p>{error}</p>
      </div>
    );
  }
  if (!stats || !users) return <p className="empty">Loading…</p>;

  const a = stats.accounts;
  const modules = Object.entries(stats.collections.owned_by_module);

  return (
    <div className="admin">
      <section className="settings-card">
        <h3>People</h3>
        <div className="admin-stats">
          <Stat label="Accounts" value={a.total} note={`${a.admins} admin`} />
          <Stat label="Confirmed" value={a.verified} note="address proven" />
          <Stat
            label="Subscribers"
            value={a.subscribers}
            note={
              // The people you gave it to are not revenue, so they are not in
              // the number — but they are on the tier, so they are said.
              `$${stats.revenue.monthly_gross_usd}/mo gross` +
              (a.comped ? ` · ${a.comped} given` : "")
            }
          />
          <Stat label="New this week" value={a.new_7d} note={`${a.new_30d} in 30 days`} />
        </div>
      </section>

      <section className="settings-card">
        <h3>What the server holds</h3>
        <div className="admin-stats">
          <Stat label="Catalogue" value={stats.catalogue.items.toLocaleString()} note="shared entries" />
          <Stat label="Copies owned" value={stats.collections.copies.toLocaleString()} note="across everybody" />
          <Stat label="Wanted" value={stats.collections.wanted.toLocaleString()} />
          <Stat label="Photographs" value={fmtBytes(stats.storage.photos_bytes)} note="on disk" />
          <Stat
            label="Barcodes cached"
            value={stats.barcodes.barcodes_known.toLocaleString()}
            note={`${stats.barcodes.unrecognised} unknown`}
          />
        </div>
        <div className="admin-modules">
          {modules.map(([m, n]) => (
            <span key={m} className={`admin-chip ${stats.install.paid_modules.includes(m) ? "paid" : ""}`}>
              {m}
              <b>{n.toLocaleString()}</b>
            </span>
          ))}
        </div>
        <p className="settings-note">
          Collections marked in gold are the ones this install charges for.
          {stats.install.open_signup
            ? " Anybody can sign themselves up."
            : " Signup is closed — accounts are invited."}
        </p>
      </section>

      <section className="settings-card">
        <h3>Accounts</h3>
        {error && (
          <p className="settings-note" style={{ color: "var(--danger, #ff8080)" }}>{error}</p>
        )}
        <div className="admin-table-wrap">
          <table className="admin-table">
            <tbody>
              <tr>
                <th>Who</th>
                <th>Joined</th>
                <th>Items</th>
                <th>Plan</th>
                <th />
              </tr>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <span className="admin-who">{u.email || `#${u.id}`}</span>
                    {u.display_name && <span className="admin-name">{u.display_name}</span>}
                    {/* The one thing about an account strangers can see,
                        which is why it is the one thing occasionally taken
                        away. Linked only where it answers: a name is claimed
                        at sign-up and a profile is published later or never,
                        so most names have no page behind them and a link to
                        one is a link to "no such profile". */}
                    {u.screen_name &&
                      (u.profile_public ? (
                        <a
                          className="admin-name"
                          href={`/u/${u.screen_name.toLowerCase()}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          /u/{u.screen_name}
                        </a>
                      ) : (
                        <span className="admin-name unpublished" title="Claimed, but nothing published yet">
                          /u/{u.screen_name} <em>unpublished</em>
                        </span>
                      ))}
                    {!u.email_verified_at && <span className="admin-flag">unconfirmed</span>}
                  </td>
                  <td className="admin-num">{fmtDate(u.created_at)}</td>
                  <td className="admin-num">{u.items.toLocaleString()}</td>
                  <td>
                    {u.is_admin ? (
                      // An admin is never billed and is on the tier anyway —
                      // both are true and the row should say both, or the
                      // owner reads their own account as free.
                      <>
                        <span className="admin-plan admin">admin</span>
                        <span className="admin-plan on">supporter</span>
                      </>
                    ) : u.subscribed ? (
                      <span className="admin-plan on">
                        supporter
                        {u.plan_until && <small> to {fmtDate(u.plan_until)}</small>}
                        {u.comped && <small> · given</small>}
                      </span>
                    ) : (
                      <span className="admin-plan">free</span>
                    )}
                  </td>
                  <td className="admin-acts">
                    {!u.is_admin && (
                      <button
                        type="button"
                        className="ghost"
                        disabled={busy === u.id}
                        onClick={() => setPlan(u.id, u.subscribed ? "free" : "supporter")}
                      >
                        {busy === u.id ? "…" : u.subscribed ? "Make free" : "Give supporter"}
                      </button>
                    )}
                    {!u.is_admin && (
                      <label className="admin-friend" title="Not counted as a subscriber">
                        <input
                          type="checkbox"
                          checked={!!u.comped}
                          disabled={busy === u.id}
                          onChange={(e) => setComped(u.id, e.target.checked)}
                        />
                        friend
                      </label>
                    )}
                    {u.screen_name && (
                      <button
                        type="button"
                        className="ghost danger"
                        disabled={busy === u.id}
                        title="Remove this screen name — permanent"
                        onClick={() => revokeName(u)}
                      >
                        Remove name
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="form-row wrap" style={{ marginTop: "var(--s-3)" }}>
          {/* One pass settles the pictures that lie: archive covers that
              never existed, and rows pointing at local files a deploy wiped
              — which is what a server without a persistent volume does.
              Live archive covers are copied in; the rest clear to the honest
              placeholder so their owners can re-pick or photograph. */}
          <button
            type="button"
            className="ghost"
            disabled={busy === "covers"}
            onClick={async () => {
              setBusy("covers");
              setError(null);
              try {
                const r = await api.adminRepairCovers();
                alert(
                  `${r.checked} checked — ${r.copied} copied in, ` +
                    `${r.cleared + (r.missing_files || 0)} cleared ` +
                    `(${r.missing_files || 0} pointed at files that no longer exist), ` +
                    `${r.kept} left for another try.`
                );
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(null);
              }
            }}
          >
            {busy === "covers" ? "Checking pictures…" : "Repair broken pictures"}
          </button>
        </div>
        <p className="settings-note">
          Granting a plan here has no end date — it stays until you take it
          back. Admins are never billed and cannot be put on a plan.
          {" "}Removing a screen name is permanent: nobody can claim it again,
          the person may choose one replacement, and their collection is not
          touched.
        </p>
      </section>

      <ReservedNames />
      <CardArt />
    </div>
  );
}
