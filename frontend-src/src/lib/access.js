const ROLE_VIEWS = {
  admin: new Set(["home", "chat", "workspaces", "activity", "models", "warsat", "archive", "trials", "settings", "agents", "sessions", "approvals", "memory", "skills", "telegram", "schedules"]),
  member: new Set(["home", "chat", "workspaces", "activity", "archive", "settings", "sessions"]),
  viewer: new Set(["home", "workspaces", "archive", "settings"]),
};

const MEMBER_SETTINGS = new Set(["accounts", "about"]);

export function normalizedRole(role) {
  return ROLE_VIEWS[role] ? role : "viewer";
}

export function canAccessView(role, view) {
  return ROLE_VIEWS[normalizedRole(role)].has(view);
}

export function canAccessRoute(role, view, section) {
  if (!canAccessView(role, view)) return false;
  return view !== "settings" || normalizedRole(role) === "admin" || MEMBER_SETTINGS.has(section || "accounts");
}

export function canRunTasks(role) {
  return normalizedRole(role) !== "viewer";
}

export function roleLabel(role) {
  return normalizedRole(role) === "admin" ? "Administrator" : normalizedRole(role) === "member" ? "Member" : "Viewer";
}
