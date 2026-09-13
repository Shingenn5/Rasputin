import { expect, test } from "@playwright/test";

const hardware = {
  ok: true,
  status: "ready",
  detectedHardware: {
    gpus: [{ name: "Campaign GPU", memoryTotalMb: 16384, memoryFreeMb: 14336 }],
  },
  capabilityProfile: {
    cpu: { memoryTotalMb: 32768, memoryAvailableMb: 24576 },
  },
};

function fixtureItem(id, overrides = {}) {
  return {
    id,
    modelId: id,
    name: id,
    source: "catalog",
    purpose: "chat",
    capabilities: ["chat"],
    deployable: true,
    recommendedProtocol: "llamaCppGgufServer",
    runtimeOptions: [{ protocolId: "llamaCppGgufServer", label: "llama.cpp GGUF" }],
    ...overrides,
  };
}

function fitFixtures(source) {
  return [
    fixtureItem(`${source}-ready`, { vramEstimateGb: 8, systemRamEstimateGb: 4, fitStatus: "ready", fitWillFit: true }),
    fixtureItem(`${source}-backend-fit`, { resourceManifest: { fit: { status: "ready" } } }),
    fixtureItem(`${source}-unknown`),
    fixtureItem(`${source}-blocked`, { fitStatus: "blocked", fitWillFit: false }),
    fixtureItem(`${source}-oversized`, { vramEstimateGb: 24, systemRamEstimateGb: 4, fitStatus: "blocked", fitWillFit: false }),
  ];
}

async function installCatalogMocks(page, catalogItems, searchItems = catalogItems, desktopOnly = true) {
  await page.route("**/api/ui/bootstrap", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const data = body.data || body;
    data.models = [];
    data.tasks = [];
    data.modelCatalog = { items: catalogItems, categories: [], runtimes: [] };
    data.security = {
      ...data.security,
      native: true,
      desktopOnly,
      allowRemoteModels: true,
      privacyLock: false,
    };
    await route.fulfill({ response, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.route("**/api/model-registry", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { models: [], providers: [] }, error: null }),
  }));
  await page.route("**/api/model-catalog?fit=true", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { items: catalogItems, categories: [], runtimes: [] }, error: null }),
  }));
  await page.route("**/api/model-catalog/search?**", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { items: searchItems, count: searchItems.length }, error: null }),
  }));
  await page.route("**/api/warsat/hardware?native_models=true", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: hardware, error: null }),
  }));
  await page.route("**/api/warsat/advisor/profiles", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { profiles: {} }, error: null }),
  }));
  await page.route("**/api/runtime/llamacpp/status", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { state: "install_required" }, error: null }),
  }));
  await page.route("**/api/models/downloads", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: [], error: null }),
  }));
}

async function openAuthenticatedDiscover(page, context, baseURL, catalogItems, searchItems, desktopOnly = true) {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated QA server");
  expect(new URL(baseURL).hostname).toBe("127.0.0.1");
  const login = await context.request.post("/api/auth/login", {
    data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  await installCatalogMocks(page, catalogItems, searchItems, desktopOnly);
  await page.addInitScript(() => localStorage.setItem("rasputin-onboarded", "1"));
  await page.goto("/#discover");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  await expect(page.locator("#modelsView").getByRole("heading", { name: "Discover Models" })).toBeVisible();
  return page.getByTestId(desktopOnly ? "discover-model-row" : "model-catalog-card");
}

async function chooseFitFilter(page, value) {
  await page.locator("details.models-catalog-advanced summary").click();
  await page.getByLabel("Hardware fit").selectOption(value);
}

async function openHardwareFilters(page) {
  await page.locator("details.model-hardware-filters summary").click();
}

test("Desktop browse keeps Any fit broad and applies Fits safely plus max-13 bounds", async ({ page, context, baseURL }) => {
  const items = fitFixtures("curated");
  const cards = await openAuthenticatedDiscover(page, context, baseURL, items, items);
  await page.getByTestId("discover-browse-models").click();
  await expect(cards).toHaveCount(5);

  await chooseFitFilter(page, "fits");
  await expect(cards).toHaveCount(2);
  await openHardwareFilters(page);
  await page.getByLabel("Maximum VRAM GB").fill("13");
  await expect(cards).toHaveCount(1);
  await expect(cards.filter({ hasText: "curated-ready" })).toHaveCount(1);
  await page.getByLabel("Maximum VRAM GB").fill("");
  await expect(cards).toHaveCount(2);
  await page.getByLabel("Hardware fit").selectOption("all");
  await expect(cards).toHaveCount(5);
  await page.screenshot({ path: test.info().outputPath("desktop-any-fit.png") });
});

test("Hugging Face results use the same fit filter for unknown and backend-positive rows", async ({ page, context, baseURL }) => {
  const items = fitFixtures("hf").map((item) => ({ ...item, source: "huggingface" }));
  const cards = await openAuthenticatedDiscover(page, context, baseURL, [], items);
  await page.getByTestId("discover-search-models").click();
  await page.getByTestId("model-specific-hf-input").fill("campaign");
  await page.getByTestId("model-specific-hf-submit").click();
  await expect(cards).toHaveCount(5);

  await chooseFitFilter(page, "fits");
  await expect(cards).toHaveCount(2);
  await expect(cards.filter({ hasText: "hf-backend-fit" })).toHaveCount(1);
  await expect(cards.filter({ hasText: "hf-ready" })).toHaveCount(1);
  await expect(cards.filter({ hasText: "hf-unknown" })).toHaveCount(0);
  await expect(cards.filter({ hasText: "hf-blocked" })).toHaveCount(0);
  await expect(cards.filter({ hasText: "hf-oversized" })).toHaveCount(0);
  await page.screenshot({ path: test.info().outputPath("desktop-fits-safely.png") });
});

test("Native Host curated catalog uses the same fit rules", async ({ page, context, baseURL }) => {
  const items = fitFixtures("local");
  const cards = await openAuthenticatedDiscover(page, context, baseURL, items, items, false);
  await page.getByRole("button", { name: "Local Catalog", exact: true }).click();
  await expect(cards).toHaveCount(5);
  await chooseFitFilter(page, "fits");
  await expect(cards).toHaveCount(2);
  await openHardwareFilters(page);
  await page.getByLabel("Maximum VRAM GB").fill("13");
  await expect(cards).toHaveCount(1);
  await expect(cards).toContainText("local-ready");
});
