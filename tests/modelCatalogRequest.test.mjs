import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const app = fs.readFileSync(new URL("../frontend-src/src/app/App.jsx", import.meta.url), "utf8");
const warsat = fs.readFileSync(new URL("../frontend-src/src/features/warsat/WarsatView.jsx", import.meta.url), "utf8");

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function createCatalogLoader({ fetchCatalog, refreshCatalog, notify }) {
  let catalog = { items: [] };
  let automaticAttempted = false;
  let inFlight = null;

  return (refresh = false, options = {}) => {
    const automatic = options?.automatic === true;
    if (inFlight) {
      if (automatic) automaticAttempted = true;
      if (!automatic) inFlight.notify = true;
      return inFlight.promise;
    }
    if (automatic && automaticAttempted) return Promise.resolve(catalog);
    if (automatic) automaticAttempted = true;
    const request = { notify: !automatic, promise: null };
    request.promise = (async () => {
      if (refresh) await refreshCatalog();
      catalog = await fetchCatalog();
      if (request.notify) notify(refresh ? "Model catalog refreshed." : "Model catalog loaded.");
      return catalog;
    })().finally(() => {
      if (inFlight === request) inFlight = null;
    });
    inFlight = request;
    return request.promise;
  };
}

test("WarSat automatic catalog loading is one-shot, silent, and explicitly marked", () => {
  assert.match(warsat, /loadModelCatalog\?\.\(false, \{ automatic: true \}\)/);
  assert.match(app, /const loadModelCatalog = useCallback\(async \(refresh = false, options = \{\}\)/);
  assert.match(app, /modelCatalogAutoAttemptedRef/);
  assert.match(app, /modelCatalogRequestRef/);
  assert.match(app, /if \(request\.notify\) \{/);
  assert.doesNotMatch(warsat, /loadModelCatalog\?\.\(\);/);
});

test("empty automatic catalog resolves once across repeated effects and concurrent calls", async () => {
  const pending = deferred();
  let requests = 0;
  const load = createCatalogLoader({
    fetchCatalog: () => { requests += 1; return pending.promise; },
    refreshCatalog: async () => {},
    notify: () => { throw new Error("automatic catalog load must be silent"); },
  });
  const first = load(false, { automatic: true });
  const second = load(false, { automatic: true });
  assert.strictEqual(first, second, "concurrent automatic calls share one promise");
  assert.equal(requests, 1);
  pending.resolve({ items: [] });
  assert.deepEqual(await first, { items: [] });
  await load(false, { automatic: true });
  assert.equal(requests, 1, "an empty success is terminal, not a retry signal");
});

test("explicit loads notify once and a later explicit refresh retries", async () => {
  let requests = 0;
  let refreshes = 0;
  const messages = [];
  const load = createCatalogLoader({
    fetchCatalog: async () => { requests += 1; return { items: [] }; },
    refreshCatalog: async () => { refreshes += 1; },
    notify: (message) => messages.push(message),
  });
  await load(false);
  await load(true);
  assert.equal(requests, 2);
  assert.equal(refreshes, 1);
  assert.deepEqual(messages, ["Model catalog loaded.", "Model catalog refreshed."]);
  await load(true);
  assert.equal(requests, 3, "a new explicit refresh can retry after an empty result");
  assert.equal(messages.length, 3);
});
