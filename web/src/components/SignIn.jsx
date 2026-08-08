import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Icon } from "./Icons.jsx";

/** The gate.
 *
 *  Wraps the whole app so nothing underneath it ever renders for a stranger,
 *  and so the rest of the code can go on assuming there is somebody there.
 *
 *  A single-user install passes straight through and never sees any of this:
 *  no form, no flash of one, not even a delay worth noticing. That is the
 *  default, and an existing install upgrading into it should not be able to
 *  tell that accounts were added at all.
 */
export default function SignIn({ children }) {
  const [state, setState] = useState(null); // null = still asking
  const [error, setError] = useState(null);

  const refresh = () =>
    api
      .authMe()
      .then(setState)
      .catch(() => setState({ multi_user: true, user: null, unreachable: true }));

  useEffect(() => {
    refresh();
  }, []);

  if (state === null) return null; // a spinner here would flicker on every load
  if (!state.multi_user || state.user) return children;

  return <Gate needsSetup={state.needs_setup} onDone={refresh} error={error} setError={setError} />;
}

function Gate({ needsSetup, onDone, error, setError }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (needsSetup) {
        await api.authSetup({ email, password, display_name: name.trim() || null });
      } else {
        await api.authLogin({ email, password });
      }
      await onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="signin-scrim">
      <form className="signin" onSubmit={submit}>
        <h1>
          <span className="brand-mark">
            <Icon id="coin" />
          </span>
          Your <b>Loot</b>
        </h1>

        {needsSetup ? (
          <p className="signin-lead">
            Accounts are on and nobody has claimed this server yet. Whatever
            you set here becomes the owner account — it already holds
            everything in the collection.
          </p>
        ) : (
          <p className="signin-lead">Sign in to your collection.</p>
        )}

        {needsSetup && (
          <input
            type="text"
            placeholder="Your name (optional)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="nickname"
          />
        )}
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
          required
        />
        <input
          type="password"
          placeholder={needsSetup ? "Choose a password (8+ characters)" : "Password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={needsSetup ? "new-password" : "current-password"}
          minLength={8}
          required
        />

        {error && (
          <span className="signin-error">
            <Icon id="alert" />
            {error}
          </span>
        )}

        <button type="submit" className="primary" disabled={busy}>
          <Icon id="check" />
          {busy ? "…" : needsSetup ? "Claim this server" : "Sign in"}
        </button>

        {/* Somebody will lock themselves out, and the answer cannot be an
            email they never configured a server to send. */}
        {!needsSetup && (
          <p className="signin-note">
            Forgotten it? There is no reset email — this is your server. Reset
            it from the host:
            <code>docker compose exec api python -m app.resetpw you@example.com</code>
          </p>
        )}
      </form>
    </div>
  );
}
