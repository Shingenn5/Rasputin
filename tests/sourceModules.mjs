import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Source contracts follow feature-local modules after component extraction.
// Cross-feature imports are excluded so unrelated screens cannot satisfy a check.
export function readFeatureSource(file) {
  const entry = file instanceof URL ? fileURLToPath(file) : path.resolve(file);
  const directory = path.dirname(entry);
  const visited = new Set();
  const read = (filename) => {
    if (visited.has(filename)) return "";
    visited.add(filename);
    const source = readFileSync(filename, "utf8");
    const imports = [...source.matchAll(/(?:import|export)[^;]*?from\s+["'](\.\/[^"']+\.(?:jsx?|mjs))["']/g)];
    return [source, ...imports.map((match) => {
      const dependency = path.resolve(path.dirname(filename), match[1]);
      return path.dirname(dependency) === directory ? read(dependency) : "";
    })].join("\n");
  };
  return read(entry);
}
