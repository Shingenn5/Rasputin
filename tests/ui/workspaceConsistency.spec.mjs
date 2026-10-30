import { expect, test } from "@playwright/test";

// Runtime/model responses are fixtures; authentication and page routing are real.
const models = [
  { key: "qa-qwen", name: "Qwen3 8B", model: "Qwen3-8B-Q4_K_M.gguf", provider: "llamacpp", runtime: "native-llamacpp", managed: true, enabled: true, runtimeStatus: "stopped", role: "main", contextWindow: 32768, hostModelPath: "C:\\QA\\Qwen3-8B-Q4_K_M.gguf", artifactAvailable: true, quantization: "Q4_K_M", sizeBytes: 5_000_000_000 },
  { key: "qa-gemma", name: "Gemma 3 4B", model: "gemma-3-4b", provider: "llamacpp", runtime: "native-llamacpp", managed: true, enabled: true, runtimeStatus: "reachable", role: "coder", contextWindow: 8192, artifactAvailable: true },
  { key: "qa-server", name: "Local coding server", model: "coder", provider: "openai-compatible", runtime: "external-local", enabled: true, runtimeStatus: "unreachable", role: "helper", baseUrl: "http://127.0.0.1:9998/v1" },
];

test.beforeEach(async ({ context, page }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated QA server");
  const login = await context.request.post("/api/auth/login", { data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD } });
  expect(login.ok()).toBeTruthy();
  await page.addInitScript(() => {
    if (!localStorage.getItem("rasputin-theme")) localStorage.setItem("rasputin-theme", "rasputin-dark");
    localStorage.setItem("rasputin-theme-explicit", "1");
    localStorage.setItem("rasputin-onboarded", "1");
    localStorage.setItem("rasputin-sidebar-collapsed", "false");
    localStorage.removeItem("rasputin-model-inspector-width");
  });
  await page.route("**/api/ui/bootstrap", async route => {
    const response = await route.fetch();
    const json = await response.json();
    json.data.security = { ...json.data.security, native: true, desktopOnly: true };
    json.data.preferences = { ...json.data.preferences, onboarded: true, selectedModel: "qa-gemma" };
    json.data.models = models;
    await route.fulfill({ json });
  });
  await page.route("**/api/model-registry", route => route.fulfill({ json: { ok: true, data: { models } } }));
  await page.route("**/api/runtime/llamacpp/status", route => route.fulfill({ json: { ok: true, data: { state: "ready", available: true } } }));
  await page.route("**/api/model-catalog/load-plan-preview", route => route.fulfill({ json: { ok: true, data: { accepted: true, blocked: false, resolvedSettings: { requiredMemoryMb: 6000 } } } }));
});

for (const width of [1440, 768, 390]) {
  test(`model selection, filtering, and inspector navigation work at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/#models");
    const rows = page.getByTestId("installed-model-row");
    await expect(rows).toHaveCount(3);
    const inspector = page.getByTestId("installed-model-inspector");
    await rows.filter({ hasText: "Qwen3 8B" }).getByRole("button", { name: /Details and settings/ }).click();
    await expect(inspector).toContainText("Qwen3 8B");
    expect((await inspector.boundingBox()).width).toBeGreaterThan(280);
    const filter = page.getByRole("searchbox", { name: "Filter installed models" });
    await filter.fill("coding server");
    await expect(rows).toHaveCount(1);
    await expect(inspector).toContainText("Local coding server");
    await filter.clear();
    await page.getByRole("button", { name: /Ready to use/ }).click();
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText("Gemma 3 4B");
    await page.getByRole("button", { name: /All models/ }).click();
    await rows.filter({ hasText: "Qwen3 8B" }).getByRole("button", { name: /Details and settings/ }).click();
    const overview = inspector.getByRole("tab", { name: "Overview", exact: true });
    await overview.focus();
    await page.keyboard.press("ArrowRight");
    await expect(inspector.getByRole("tab", { name: "Load settings", exact: true })).toBeFocused();
    await expect(inspector.getByRole("tabpanel")).toContainText("Automatic placement");
    await overview.click();
    await page.screenshot({ path: test.info().outputPath(`model-hub-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  });

  test(`simple load settings preserve hidden advanced values at ${width}px`, async ({ page }) => {
    let submitted;
    await page.route("**/api/model-registry/start", async route => {
      submitted = route.request().postDataJSON();
      await route.fulfill({ json: { ok: true, data: {} } });
    });
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/#models");
    await page.getByTestId("installed-model-row").filter({ hasText: "Qwen3 8B" }).getByRole("button", { name: "Load model", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Qwen3 8B", exact: true });
    await expect(dialog.getByLabel("Context length")).toBeVisible();
    await expect(dialog.getByLabel("CPU thread pool")).toHaveCount(0);
    await dialog.getByRole("button", { name: "Show advanced settings" }).click();
    await dialog.getByLabel("CPU thread pool").fill("8");
    await dialog.getByRole("button", { name: "Hide advanced settings" }).click();
    await dialog.getByRole("button", { name: "Lower memory", exact: true }).click();
    await expect(dialog.getByLabel("Context length")).toHaveValue("4096");
    await expect(dialog.getByRole("button", { name: "Load model", exact: true })).toBeEnabled();
    const bounds = await dialog.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
    expect(await dialog.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(false);
    const cancelBounds = await dialog.getByRole("button", { name: "Cancel", exact: true }).boundingBox();
    const loadBounds = await dialog.getByRole("button", { name: "Load model", exact: true }).boundingBox();
    expect(Math.abs(cancelBounds.y - loadBounds.y)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: test.info().outputPath(`model-load-${width}.png`) });
    await dialog.getByRole("button", { name: "Load model", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    expect(submitted).toMatchObject({ key: "qa-qwen", profile: { contextLength: 4096, threads: 8, cacheTypeK: "q8_0", cacheTypeV: "q8_0" } });
  });
}

test("secondary routes stay within the viewport in both themes", async ({ page }) => {
  test.setTimeout(120000);
  const routes = ["api", "training", "schedules", "archive", "assistant", "workspaces", "skills", "activity", "models", "settings/general"];
  for (const [theme, widths] of [["rasputin-dark", [1440, 768, 390]], ["rasputin-light", [1440, 390]]]) {
    await page.goto("/#chat");
    await page.locator("body[data-ready='true']").waitFor();
    await page.evaluate(value => {
      localStorage.setItem("rasputin-theme", value);
      window.rasputinTheme.apply(value);
    }, theme);
    for (const width of widths) {
      await page.setViewportSize({ width, height: 1000 });
      for (const route of routes) {
        await page.goto(`/#${route}`);
        const surface = route.startsWith("settings") ? page.getByRole("dialog", { name: "Settings", exact: true }) : page.locator(".app-view.active");
        await expect(surface).toBeVisible();
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `${route}, ${theme}, ${width}`).toBe(false);
        expect(await surface.evaluate(element => element.scrollWidth - element.clientWidth), `${route} content, ${theme}, ${width}`).toBeLessThanOrEqual(1);
        if (["api", "training", "schedules", "archive"].includes(route)) {
          await page.screenshot({ path: test.info().outputPath(`${route}-${theme}-${width}.png`) });
        }
      }
    }
  }
});

test("all model areas remain usable at desktop tablet and phone widths", async ({ page }) => {
  test.setTimeout(90000);
  const areas = [["Discover", "library"], ["My Models", "installed"], ["Loaded", "running"], ["Share models", "serving"], ["Advanced", "settings"]];
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/#models");
    const navigation = page.getByRole("tablist", { name: "Model management areas" });
    for (const [name, id] of areas) {
      const tab = navigation.getByRole("tab", { name, exact: true });
      await tab.click();
      await expect(tab).toHaveAttribute("aria-selected", "true");
      const panel = page.locator(`#models-panel-${id}`);
      await expect(panel).toBeVisible();
      expect(await panel.evaluate(element => element.scrollWidth - element.clientWidth), `${name} at ${width}`).toBeLessThanOrEqual(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
      await page.screenshot({ path: test.info().outputPath(`models-${id}-${width}.png`) });
    }
  }
});
