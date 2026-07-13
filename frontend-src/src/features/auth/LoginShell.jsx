import React from "react";
import { ArrowRight, Box, KeyRound, Laptop, LockKeyhole, ShieldCheck } from "lucide-react";

export function LoginShell({ onSubmit, status }) {
  return (
    <section className="login-shell" id="loginShell">
      <div className="login-grid" data-testid="login-card">
        <aside className="login-manifesto" aria-label="About Rasputin">
          <div className="login-brand-lockup">
            <div className="ras-brand-sigil ras-brand-sigil-lg" aria-hidden="true"><span>R</span><i /></div>
            <div>
              <strong>Rasputin</strong>
              <span>Private AI operations</span>
            </div>
          </div>

          <div className="login-manifesto-copy">
            <p className="login-kicker">LOCAL CONTROL PLANE</p>
            <h1>Your models.<br />Your machine.<br /><em>Your rules.</em></h1>
            <p>
              A focused workspace for private model orchestration, coding tasks, and
              evidence-backed automation.
            </p>
          </div>

          <ul className="login-principles">
            <li><ShieldCheck size={16} aria-hidden="true" /><span><strong>Private by default</strong>Data stays under operator control.</span></li>
            <li><Laptop size={16} aria-hidden="true" /><span><strong>Native workstation</strong>Direct folders and the host toolchain.</span></li>
            <li><Box size={16} aria-hidden="true" /><span><strong>Docker server</strong>The same wrapper, deployable as infrastructure.</span></li>
          </ul>
        </aside>

        <div className="login-card">
          <form onSubmit={onSubmit} data-testid="login-form">
            <header className="login-form-header">
              <div className="login-access-icon" aria-hidden="true"><LockKeyhole size={18} /></div>
              <div>
                <p className="login-kicker">OPERATOR ACCESS</p>
                <h2>Welcome back</h2>
              </div>
            </header>

            <p className="login-form-intro">Sign in with your local account for this Rasputin runtime.</p>

            <label className="login-field" htmlFor="loginUsername">
              <span>Username</span>
              <input id="loginUsername" name="username" autoComplete="username" spellCheck="false" autoFocus />
            </label>

            <label className="login-field" htmlFor="loginPassword">
              <span>Password</span>
              <input id="loginPassword" name="password" type="password" autoComplete="current-password" required autoFocus />
            </label>

            <button className="login-submit" type="submit">
              <span>Enter workspace</span>
              <ArrowRight size={17} aria-hidden="true" />
            </button>

            {status && <p className="login-status" role="status" aria-live="polite">{status}</p>}

            <details className="login-recovery">
              <summary><KeyRound size={14} aria-hidden="true" /> Can&apos;t find your password?</summary>
              <div>
                <p>First-run credentials appear in the terminal that launched Rasputin. If the original log is gone, reset the local admin password:</p>
                <code>.\rasputin.ps1 reset-password</code>
                <span>Native launch: <code>python -m backend.tools.reset_password</code></span>
              </div>
            </details>

            <footer className="login-local-note"><span aria-hidden="true" /> Credentials are verified locally and never sent to a model.</footer>
          </form>
        </div>
      </div>
    </section>
  );
}
