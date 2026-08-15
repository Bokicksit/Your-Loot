import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
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
  const { pathname } = useLocation();

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

  // A link from an email arrives at a browser that is signed out — that is
  // the whole point of it. Meeting it with a login form would be asking for
  // the password the person is here because they have forgotten. So these two
  // are decided before anything else, and before /me has even answered.
  if (pathname === "/verify") return <VerifyScreen onDone={refresh} />;
  if (pathname === "/reset") return <ResetScreen />;

  if (state === null) return null; // a spinner here would flicker on every load
  if (state.unreachable) return <Unreachable detail={state.unreachable} onRetry={refresh} />;
  if (state.user) return children;
  if (!state.multi_user && !state.locked) return children;

  return (
    <Gate
      needsSetup={state.needs_setup}
      // one account: the address is implied, so the form is one field
      soloLock={!state.multi_user}
      openSignup={state.open_signup}
      canEmail={state.email_enabled}
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

/** Confirming an address, from the link in the welcome email. */
function VerifyScreen({ onDone }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [result, setResult] = useState(null); // null = still going

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setResult({ error: "That link is missing its code." });
      return;
    }
    api
      .authVerify(token)
      .then(() => setResult({ ok: true }))
      .catch((e) => setResult({ error: e.message }));
  }, [params]);

  return (
    <div className="signin-scrim">
      <div className="signin">
        <h1>
          <span className="brand-mark">
            <BrandMark size={26} />
          </span>
          Your <b>Loot</b>
        </h1>
        {result === null && <p className="signin-lead">Confirming your address…</p>}
        {result?.ok && (
          <>
            <p className="signin-lead">
              That's confirmed — thank you. Your address can now be used to
              reset your password if you ever need it.
            </p>
            <button
              type="button"
              className="primary"
              onClick={async () => {
                await onDone();
                navigate("/");
              }}
            >
              <Icon id="check" />
              Continue
            </button>
          </>
        )}
        {result?.error && (
          <>
            <span className="signin-error">
              <Icon id="alert" />
              {result.error}
            </span>
            <p className="signin-note">
              Links last a day and can only be used once. Sign in and ask for
              another from your settings.
            </p>
            <button type="button" className="primary" onClick={() => navigate("/")}>
              Go to sign in
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/** Choosing a new password, from the link in a reset email. */
function ResetScreen() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const token = params.get("token");

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.authReset(token, password);
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="signin-scrim">
        <div className="signin">
          <h1>
            <span className="brand-mark">
              <BrandMark size={26} />
            </span>
            Your <b>Loot</b>
          </h1>
          <p className="signin-lead">
            Your password has been changed. Sign in with the new one.
          </p>
          <button type="button" className="primary" onClick={() => navigate("/")}>
            <Icon id="check" />
            Sign in
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="signin-scrim">
      <form className="signin" onSubmit={submit}>
        <h1>
          <span className="brand-mark">
            <BrandMark size={26} />
          </span>
          Your <b>Loot</b>
        </h1>
        <p className="signin-lead">Choose a new password.</p>
        <input
          type="password"
          placeholder="New password (8+ characters)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          minLength={8}
          required
          autoFocus
        />
        {error && (
          <span className="signin-error">
            <Icon id="alert" />
            {error}
          </span>
        )}
        <button type="submit" className="primary" disabled={busy || !token}>
          <Icon id="check" />
          {busy ? "…" : "Set password"}
        </button>
        {!token && (
          <p className="signin-note">That link is missing its code.</p>
        )}
      </form>
    </div>
  );
}

function Gate({ needsSetup, soloLock, openSignup, canEmail, onDone, error, setError }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  // signin | signup | forgot. Only ever leaves "signin" where the server said
  // it offers accounts to anybody.
  const [mode, setMode] = useState("signin");
  const [sent, setSent] = useState(false);

  const go = (next) => {
    setMode(next);
    setError(null);
    setSent(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (needsSetup) {
        await api.authSetup({ email, password, display_name: name.trim() || null });
      } else if (mode === "signup") {
        await api.authSignup({ email, password, display_name: name.trim() || null });
      } else if (mode === "forgot") {
        await api.authForgot(email);
        setSent(true);
        return; // nothing to sign in to yet
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

  // The reset email has been asked for. Deliberately says nothing about
  // whether that address had an account — the server does not tell us, on
  // purpose, and inventing an answer here would give away what it protects.
  if (sent) {
    return (
      <div className="signin-scrim">
        <div className="signin">
          <h1>
            <span className="brand-mark">
              <BrandMark size={26} />
            </span>
            Your <b>Loot</b>
          </h1>
          <p className="signin-lead">
            If there's an account for {email}, a reset link is on its way. It
            lasts an hour.
          </p>
          <button type="button" className="primary" onClick={() => go("signin")}>
            Back to sign in
          </button>
        </div>
      </div>
    );
  }

  const heading = needsSetup
    ? "Claim this server"
    : mode === "signup"
      ? "Create an account"
      : mode === "forgot"
        ? "Send a reset link"
        : "Unlock";

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
        ) : mode === "signup" ? (
          <p className="signin-lead">
            Your collection, kept for you. We'll send one email to confirm the
            address and nothing else.
          </p>
        ) : mode === "forgot" ? (
          <p className="signin-lead">
            Your address, and we'll send a link to set a new password.
          </p>
        ) : (
          <p className="signin-lead">Sign in to your collection.</p>
        )}

        {(needsSetup || mode === "signup") && (
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
        {mode !== "forgot" && (
          <input
            type="password"
            placeholder={
              needsSetup || mode === "signup"
                ? "Choose a password (8+ characters)"
                : "Password or PIN"
            }
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={
              needsSetup || mode === "signup" ? "new-password" : "current-password"
            }
            minLength={needsSetup || mode === "signup" ? 8 : 4}
            required
            autoFocus={soloLock}
          />
        )}

        {error && (
          <span className="signin-error">
            <Icon id="alert" />
            {error}
          </span>
        )}

        <button type="submit" className="primary" disabled={busy}>
          <Icon id="check" />
          {busy ? "…" : heading}
        </button>

        {/* Two separate questions, and they were the same flag once, which
            was wrong: whether strangers may join, and whether this server can
            send an email. A family install with a provider configured wants
            resets without wanting signups. */}
        {!needsSetup && (canEmail || openSignup) && (
          <p className="signin-alt">
            {mode === "signin" ? (
              <>
                {canEmail && (
                  <button type="button" className="linkish" onClick={() => go("forgot")}>
                    Forgotten your password?
                  </button>
                )}
                {openSignup && (
                  <button type="button" className="linkish" onClick={() => go("signup")}>
                    Create an account
                  </button>
                )}
              </>
            ) : (
              <button type="button" className="linkish" onClick={() => go("signin")}>
                Back to sign in
              </button>
            )}
          </p>
        )}

        {/* Somebody will lock themselves out, and on a server that cannot
            send mail the answer cannot be an email. Shown exactly when there
            is no reset link above to contradict it. */}
        {!needsSetup && !canEmail && (
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
