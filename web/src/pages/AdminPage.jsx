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
        <p className="settings-note">
          Granting a plan here has no end date — it stays until you take it
          back. Admins are never billed and cannot be put on a plan.
          {" "}Removing a screen name is permanent: nobody can claim it again,
          the person may choose one replacement, and their collection is not
          touched.
        </p>
      </section>
    </div>
  );
}
