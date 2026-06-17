export const navItems = [
  { view: "home", label: "Home", testId: "nav-home" },
  { view: "workspaces", label: "Workspaces", testId: "nav-workspaces" },
  { view: "activity", label: "Activity", testId: "nav-activity" },
  { view: "models", label: "Models", testId: "nav-models" },
  { view: "warsat", label: "Warsat", testId: "nav-warsat" },
  { view: "archive", label: "Archive", testId: "nav-archive" },
  { view: "trials", label: "Trials", testId: "nav-trials" },
  { view: "settings", section: "general", label: "Settings", testId: "nav-settings" },
];

export const settingsItems = [
  ["general", "General", "platform defaults"],
  ["runtime", "Runtime", "system limits"],
  ["security", "Security", "keys & secrets"],
  ["models", "Models", "AI governance"],
  ["deployments", "Deployments", "WarSat rules"],
  ["integrations", "Integrations", "external systems"],
  ["resources", "Resources", "hardware limits"],
  ["notifications", "Notifications", "alerts"],
  ["audit", "Audit", "compliance"],
  ["diagnostics", "Diagnostics", "health checks"],
  ["about", "About", "platform info"],
];

export const themeOptions = [
  ["cyberpunk-neon", "Cyberpunk Neon", "Vibrant synthwave dark theme"],
  ["ocean-abyss", "Ocean Abyss", "Deep dark blue and aqua"],
  ["hacker-matrix", "Hacker Matrix", "Monochrome black and terminal green"],
  ["crimson-forge", "Crimson Forge", "Dark grey and intense red"],
  ["nord-frost", "Nord Frost", "Cool arctic blues and grays"],
  ["rasputin-light", "Rasputin Light", "Warm graphite on light shell"],
  ["rasputin-dark", "Rasputin Dark", "Default Warmind dark"],
  ["bootswatch-slate", "Slate Ops", "Bootswatch Slate inspired"],
  ["bootswatch-cyborg", "Cyborg Redline", "Bootswatch Cyborg inspired"],
  ["bootswatch-darkly", "Darkly Forge", "Bootswatch Darkly inspired"],
  ["bootswatch-lux", "Lux Archive", "Bootswatch Lux inspired"],
  ["bootswatch-solar", "Solar Archive", "Bootswatch Solar inspired"],
  ["bootswatch-superhero", "Superhero Night", "Bootswatch Superhero inspired"],
  ["contrast", "High Contrast", "Accessibility-first contrast"],
];

export const darkThemes = new Set([
  "cyberpunk-neon",
  "ocean-abyss",
  "hacker-matrix",
  "crimson-forge",
  "nord-frost",
  "rasputin-dark",
  "bootswatch-slate",
  "bootswatch-cyborg",
  "bootswatch-darkly",
  "bootswatch-solar",
  "bootswatch-superhero",
]);

export const quickPrompts = [
  ["Analyze Files", "Summarize this workspace and tell me what looks important.", "analyze files"],
  ["Organize", "Draft a safe folder organization plan for this workspace. Do not move anything yet.", "organize"],
  ["Research", "Search the approved local knowledge and cite the files you used.", "research"],
  ["Think", "Help me reason through this problem step by step.", "chat"],
];
