import { useState, useRef } from "react";
import { ProjectIdentity, ProjectCredits } from "../../shared/Branding.jsx";

export function LoginScreen({ onLogin, toast, onDismissError, authState, onRetryAuth, onUseLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const loginLock = useRef(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loginLock.current) return;
    loginLock.current = true;
    setPending(true);
    try { await onLogin(username, password); }
    finally { loginLock.current = false; setPending(false); }
  };

  return (
    <div className="login-page">
      <div className="login-layout">
        <section className="login-brand" aria-label="BillTrack billing portal">
          <div className="login-visual" aria-hidden="true">
            <div className="login-visual-back" />
            <img src="/static/billtrack-logo.png" alt="" />
          </div>
          <h1>Every bill. Every payment. In view.</h1>
          <ProjectIdentity />
        </section>
        <section className="login-panel" aria-label="Sign in">
          <div className="login-panel-mark"><img src="/static/billtrack-icon.png" alt="BillTrack" /><span>BILLTRACK</span></div>
          <h2>Welcome back</h2>
          <p>Sign in to your billing workspace.</p>
          {toast && !toast.ok && <div className="error-message" role="alert"><p>{toast.msg}</p><button type="button" className="error-dismiss" aria-label="Dismiss error" onClick={onDismissError}>Dismiss</button></div>}
          {authState.pending ? <p role="status">Checking your saved sign-in…</p> : authState.error ? <div className="error-message" role="alert"><p>{authState.error}</p><p>Your saved sign-in has been kept.</p><button type="button" onClick={onRetryAuth}>Retry sign-in check</button><button type="button" className="error-dismiss" onClick={onUseLogin}>Use another sign-in</button></div> : <form onSubmit={handleSubmit} aria-busy={pending}>
            <label htmlFor="login-username">Username or email</label>
            <input id="login-username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required />
            <label htmlFor="login-password">Password</label>
            <input id="login-password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
            <button type="submit" disabled={pending}>{pending ? "Signing in…" : <>Sign in <span aria-hidden="true">→</span></>}</button>
            <a className="login-recovery" href="/admin/password-reset/totp/">Forgot password? Use authenticator</a>
            <a className="login-recovery" href="/accounts/password-reset/">Reset password by email</a>
            <a className="login-recovery" href="/accounts/signup/">Create account</a>
            <a className="login-recovery" href="/accounts/verify-email/">Verify an existing account email</a>
          </form>}
        </section>
        <ProjectCredits />
      </div>
      {toast?.ok && (
        <div className="login-toast" role="status" style={{ borderColor: toast.ok ? "#22c55e" : "#ef4444", color: toast.ok ? "#22c55e" : "#f87171" }}>
          {toast.ok ? "✓" : "✗"} {toast.msg}
        </div>
      )}
    </div>
  );
}
