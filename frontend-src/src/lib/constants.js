export const navItems = [
  { view: "home", label: "Home", testId: "nav-home" },
  { view: "workspaces", label: "Workspaces", testId: "nav-workspaces" },
  { view: "activity", label: "Activity", testId: "nav-activity" },
  { view: "settings", section: "knowledge", label: "Knowledge", testId: "nav-knowledge" },
  { view: "settings", section: "models", label: "Models", testId: "nav-models" },
  { view: "warsat", label: "Warsat", testId: "nav-warsat" },
  { view: "settings", section: "general", label: "Settings", testId: "nav-settings" },
];

export const settingsItems = [
  ["general", "General", "task defaults"],
  ["workspaces", "Workspaces", "folder access"],
  ["models", "Models", "runtime"],
  ["safety", "Safety", "permissions"],
  ["knowledge", "Knowledge", "RAG + graph"],
  ["output", "Output", "markdown"],
  ["appearance", "Appearance", "themes"],
  ["admin", "Admin", "session"],
];

export const quickPrompts = [
  ["Analyze Files", "Summarize this workspace and tell me what looks important.", "analyze files"],
  ["Organize", "Draft a safe folder organization plan for this workspace. Do not move anything yet.", "organize"],
  ["Research", "Search the approved local knowledge and cite the files you used.", "research"],
  ["Think", "Help me reason through this problem step by step.", "chat"],
];
