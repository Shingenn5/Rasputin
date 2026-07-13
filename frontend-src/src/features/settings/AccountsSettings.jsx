import React, { useEffect, useState } from "react";
import { AlertTriangle, Check, KeyRound, ShieldCheck, UserPlus, Users } from "lucide-react";
import { api, postJson } from "../../api/client.js";

export function AccountsSettings({ session }) {
  const [users, setUsers] = useState([]);
  const [workspaces, setWorkspaces] = useState([]);
  const [status, setStatus] = useState("");
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const isAdmin = session?.role === "admin";

  async function refresh() {
    if (!isAdmin) return;
    try {
      const [result, workspaceResult] = await Promise.all([api("/api/auth/users"), api("/api/workspaces")]);
      setUsers(result.users || []);
      setWorkspaces(workspaceResult.workspaces || []);
    } catch (error) {
      setStatus(error.message);
    }
  }

  useEffect(() => { refresh(); }, [isAdmin]);

  async function createAccount(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setStatus("Creating account…");
    try {
      await postJson("/api/auth/users", { username: form.get("username"), password: form.get("password"), role: form.get("role") });
      event.currentTarget.reset();
      setStatus("Account created. Access to workspaces must be granted separately.");
      await refresh();
    } catch (error) { setStatus(error.message); }
  }

  async function updateAccount(username, patch) {
    try {
      await api(`/api/auth/users/${encodeURIComponent(username)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) });
      setStatus(`${username} updated.`);
      await refresh();
    } catch (error) { setStatus(error.message); }
  }

  async function resetPassword(username) {
    try {
      const result = await postJson(`/api/auth/users/${encodeURIComponent(username)}/reset-password`, {});
      setTemporaryPassword(`${result.username}: ${result.password}`);
      setStatus("Password reset. Existing sessions for that account were revoked.");
    } catch (error) { setStatus(error.message); }
  }

  async function setWorkspaceRole(workspaceId, username, role) {
    try {
      await postJson("/api/workspace/members", { workspaceId, username, role: role || null });
      setStatus(`${username}'s workspace access was updated.`);
      await refresh();
    } catch (error) { setStatus(error.message); }
  }

  async function changeOwnPassword(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await postJson("/api/auth/change-password", { currentPassword: form.get("currentPassword"), newPassword: form.get("newPassword") });
      setStatus("Password changed. Sign in again with the new password.");
      event.currentTarget.reset();
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) { setStatus(error.message); }
  }

  return (
    <section className="settings-pane active accounts-settings" data-testid="accounts-settings">
      <div className="settings-module-title">
        <div><Users size={22} /><span><h3>Local accounts</h3><p>Identities are stored only on this Rasputin appliance.</p></span></div>
        <span className="account-current"><ShieldCheck size={14} /> {session?.username || "local user"} · {session?.role || "member"}</span>
      </div>

      {status && <div className="account-status" role="status">{status}</div>}
      {temporaryPassword && <div className="account-secret"><AlertTriangle size={16} /><span><strong>Copy this temporary password now</strong><code>{temporaryPassword}</code></span></div>}

      {isAdmin && (
        <>
          <form className="account-create-grid" onSubmit={createAccount}>
            <label><span>Username</span><input name="username" required minLength="2" maxLength="48" autoComplete="off" /></label>
            <label><span>Initial password</span><input name="password" type="password" required minLength="10" autoComplete="new-password" /></label>
            <label><span>Appliance role</span><select name="role" defaultValue="member"><option value="member">Member</option><option value="viewer">Viewer</option><option value="admin">Administrator</option></select></label>
            <button type="submit"><UserPlus size={16} /> Create account</button>
          </form>

          <div className="account-list">
            {users.map((user) => (
              <article className="account-row" key={user.username}>
                <span className="account-avatar">{user.username.slice(0, 2).toUpperCase()}</span>
                <span className="account-identity"><strong>{user.username}</strong><small>{user.enabled ? "Active" : "Disabled"}</small></span>
                <select value={user.role} aria-label={`Role for ${user.username}`} disabled={user.username === session?.username} onChange={(event) => updateAccount(user.username, { role: event.target.value })}>
                  <option value="viewer">Viewer</option><option value="member">Member</option><option value="admin">Administrator</option>
                </select>
                <button type="button" onClick={() => resetPassword(user.username)}><KeyRound size={14} /> Reset password</button>
                <button type="button" className={user.enabled ? "is-danger" : ""} disabled={user.username === session?.username} onClick={() => updateAccount(user.username, { enabled: !user.enabled })}>
                  {user.enabled ? "Disable" : "Enable"}
                </button>
              </article>
            ))}
          </div>

          <div className="workspace-access-matrix">
            <div className="workspace-access-heading"><ShieldCheck size={18} /><span><strong>Workspace access</strong><small>Appliance roles do not automatically grant folder access.</small></span></div>
            {workspaces.map((workspace) => (
              <article key={workspace.id}>
                <div><strong>{workspace.name}</strong><small>{workspace.root}</small></div>
                {users.filter((user) => user.enabled).map((user) => (
                  <label key={user.username}><span>{user.username}</span><select value={workspace.members?.[user.username] || ""} onChange={(event) => setWorkspaceRole(workspace.id, user.username, event.target.value)}>
                    <option value="">No access</option><option value="viewer">Viewer</option><option value="contributor">Contributor</option><option value="developer">Developer</option><option value="owner">Owner</option>
                  </select></label>
                ))}
              </article>
            ))}
          </div>
        </>
      )}

      <form className="account-password-form" onSubmit={changeOwnPassword}>
        <div><KeyRound size={18} /><span><strong>Change your password</strong><small>This revokes your other signed-in sessions.</small></span></div>
        <input name="currentPassword" type="password" placeholder="Current password" required autoComplete="current-password" />
        <input name="newPassword" type="password" placeholder="New password (10+ characters)" required minLength="10" autoComplete="new-password" />
        <button type="submit"><Check size={15} /> Update password</button>
      </form>
    </section>
  );
}
