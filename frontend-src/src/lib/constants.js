export const settingsItems = [
  ["general", "General", "platform defaults"],
  ["runtime", "Runtime", "system limits"],
  ["security", "Security", "keys & secrets"],
  ["accounts", "Accounts", "users & access"],
  ["models", "Models", "AI governance"],
  ["deployments", "Deployments", "WarSat rules"],
  ["integrations", "Integrations", "external systems"],
  ["mcp", "MCP Servers", "tools & servers"],
  ["resources", "Resources", "hardware limits"],
  ["notifications", "Notifications", "alerts"],
  ["audit", "Audit", "compliance"],
  ["diagnostics", "Diagnostics", "health checks"],
  ["about", "About", "platform info"],
];

// Keep the full settings catalog and its route ids stable, while giving the
// normal settings surface a smaller, outcome-oriented starting point.
export const settingsEssentialIds = ["general", "models", "runtime", "resources", "integrations", "mcp"];

export const themeOptions = [
  ["cyberpunk-neon", "Cyberpunk Neon", "Vibrant synthwave dark theme"],
  ["ocean-abyss", "Ocean Abyss", "Deep dark blue and aqua"],
  ["hacker-matrix", "Hacker Matrix", "Monochrome black and terminal green"],
  ["crimson-forge", "Crimson Forge", "Dark grey and intense red"],
  ["nord-frost", "Nord Frost", "Cool arctic blues and grays"],
  ["violet-circuit", "Violet Circuit", "Deep violet with electric lavender"],
  ["evergreen-console", "Evergreen Console", "Forest dark with calm green"],
  ["ember-noir", "Ember Noir", "Warm charcoal and ember orange"],
  ["porcelain-blue", "Porcelain Blue", "Airy cool light with steel blue"],
  ["sepia-studio", "Sepia Studio", "Warm paper with earthen copper"],
  ["orchid-paper", "Orchid Paper", "Soft neutral light with muted plum"],
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
  "violet-circuit",
  "evergreen-console",
  "ember-noir",
  "rasputin-dark",
  "bootswatch-slate",
  "bootswatch-cyborg",
  "bootswatch-darkly",
  "bootswatch-solar",
  "bootswatch-superhero",
]);
