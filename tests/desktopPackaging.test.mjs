import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const testsDirectory = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(testsDirectory, '..');
const readJson = (relativePath) => JSON.parse(fs.readFileSync(path.join(repoRoot, relativePath), 'utf8'));
const exists = (relativePath) => fs.existsSync(path.join(repoRoot, relativePath));

test('desktop packaging scripts and resources are wired', () => {
  const packageJson = readJson('package.json');
  const scripts = packageJson.scripts ?? {};
  const extraResources = packageJson.build?.extraResources ?? [];
  const resourceSources = extraResources.map((resource) => resource.from);

  assert.match(scripts['desktop:package:dir'] ?? '', /electron-builder\s+--dir\s+--win/, 'desktop:package:dir must build a Windows unpacked desktop package');
  assert.match(scripts['desktop:package'] ?? '', /electron-builder\s+--win\s+nsis/, 'desktop:package must build the Windows NSIS installer');
  assert.ok(resourceSources.includes('runtime/llama'), 'electron-builder must package runtime/llama as an extra resource');
  assert.ok(resourceSources.includes('dist/desktop-backend/rasputin-backend'), 'electron-builder must package the PyInstaller backend resource');
});

test('packaged llama runtime manifest declares CPU, CUDA, and companion assets', () => {
  const manifest = readJson(path.join('runtime', 'llama', 'manifest.json'));
  assert.ok(Array.isArray(manifest.runtimes) && manifest.runtimes.length > 0, 'runtime manifest must declare at least one runtime');

  const accelerators = new Set(manifest.runtimes.map((runtime) => runtime.accelerator));
  assert.ok(accelerators.has('cpu'), 'runtime manifest must include a CPU runtime');
  assert.ok([...accelerators].some((accelerator) => accelerator.startsWith('cuda')), 'runtime manifest must include a CUDA runtime');

  for (const runtime of manifest.runtimes.filter((entry) => entry.accelerator?.startsWith('cuda'))) {
    const names = (runtime.assets ?? []).map((asset) => asset.name);
    assert.ok(names.some((name) => name.startsWith('cudart-')), `${runtime.manifest_id} must include a companion cudart asset`);
  }
});

test('desktop-only entrypoint and backend supervisor are present', () => {
  for (const relativePath of ['desktop/main.cjs', 'desktop/backend-supervisor.cjs', 'desktop/settings.cjs']) {
    assert.ok(exists(relativePath), `required desktop file is missing: ${relativePath}`);
  }
});
