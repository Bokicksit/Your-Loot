import { useEffect, useState } from "react";
import { api } from "../api.js";
import { BrandMark, Icon } from "./Icons.jsx";

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
      // Not knowing is not the same as being signed out. This used to assume
      // multi-user and put up an email-and-password form, which asks somebody
      // to sign in to a server that isn't answering — the credentials can't
      // work, and the real fault is hidden behind a login screen.
      .catch((e) => setState({ unreachable: e.message || "no answer" }));

  useEffect(() => {
    refresh();
  }, []);

  if (state === null) return null; // a spinner here would flicker on every load
  if (state.unreachable) return <Unreachable detail={state.unreachable} onRetry={refresh} />;
  if (state.user) return children;
  if (!state.multi_user && !state.locked) return children;

  return (
    <Gate
      needsSetup={state.needs_setup}
      // one account: the address is implied, so the form is one field
      soloLock={!state.multi_user}
      onDone={refresh}
      error={error}
      setError={setError}
    />
  );
}

/** The API didn't answer.
 *
 *  Nearly always one of two things on a self-hosted install: the API container
 *  is still starting, or it's a different version from the web container —
 *  which is what happens when one image pulls and the other doesn't.
 */
function Unreachable({ detail, onRetry }) {
  return (
    <div className="signin-scrim">
      <div className="signin">
        <h1>
          <span className="brand-mark">
            <Icon id="alert" />
          </span>
          Can't reach the server
        </h1>
        <p className="signin-lead">
          The app loaded but the API didn't answer. It's usually still starting
          — give it a moment and try again.
        </p>
        <button type="button" className="primary" onClick={onRetry}>
          <Icon id="check" />
          Try again
        </button>
        <p className="signin-note">
          Still failing? Check both containers are on the same version:
          <code>docker compose ps</code>
          then
          <code>docker compose logs api --tail=50</code>
          <br />
          Mismatched versions — one image updated and the other not — look
          exactly like this.
        </p>
        {detail && <p className="signin-note">Reported: {detail}</p>}
      </div>
    </div>
  );
}

function Gate({ needsSetup, soloLock, onDone, error, setError }) {
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
        await api.authLogin(soloLock ? { password } : { email, password });
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
            <BrandMark size={26} />
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
        {!soloLock && (
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            required
          />
        )}
        <input
          type="password"
          placeholder={
            needsSetup ? "Choose a password (8+ characters)" : "Password or PIN"
          }
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={needsSetup ? "new-password" : "current-password"}
          minLength={needsSetup ? 8 : 4}
          required
          autoFocus={soloLock}
        />

        {error && (
          <span className="signin-error">
            <Icon id="alert" />
            {error}
          </span>
        )}

        <button type="submit" className="primary" disabled={busy}>
          <Icon id="check" />
          {busy ? "…" : needsSetup ? "Claim this server" : "Unlock"}
        </button>

        {/* Somebody will lock themselves out, and the answer cannot be an
            email they never configured a server to send. */}
        {!needsSetup && (
          <p className="signin-note">
            Forgotten it? There is no reset email — this is your server. Reset
            it from the host:
            <code>
              {soloLock
                ? "docker compose exec api python -m app.resetpw --clear"
                : "docker compose exec api python -m app.resetpw you@example.com"}
            </code>
          </p>
        )}
      </form>
    </div>
  );
}
