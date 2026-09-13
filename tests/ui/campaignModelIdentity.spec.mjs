import { expect, test } from "@playwright/test";

test("chat shows readable artifact names and excludes known model mismatches", async ({ page, context, baseURL }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated QA server");
  expect(new URL(baseURL).hostname).toBe("127.0.0.1");
  const login = await context.request.post("/api/auth/login", {
    data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  const model = { key: "artifact-artifact-fixture", model: "Qwen3-1.7B-Q4_K_M.gguf", name: "Qwen test", provider: "llamacpp", runtime: "native-llamacpp", runtimeStatus: "reachable", role: "main", enabled: true };
  const wrong = { ...model, key: "bad-endpoint", model: "missing-model", discoveredModels: ["different-model"] };
  await page.route("**/api/ui/bootstrap", async route => {
    const response = await route.fetch();
    const body = await response.json();
    const data = body.data || body;
    data.models = [model, wrong];
    data.tasks = [];
    data.preferences = { ...data.preferences, testingMode: false, taskMode: "chat" };
    data.security = { ...data.security, native: true, desktopOnly: true };
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/model-registry", route => route.fulfill({ json: { ok: true, data: { models: [model, wrong], providers: [] } } }));
  await page.addInitScript(() => localStorage.setItem("rasputin-onboarded", "1"));
  await page.goto("/#chat");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  await page.getByTestId("header-model-indicator").click();
  const panel = page.getByTestId("model-side-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId("model-option")).toHaveCount(1);
  await panel.getByTestId("model-option").click();
  await expect(page.getByTestId("header-model-indicator")).toContainText(model.model);
  await expect(page.locator(".composer-chip-model-name")).toContainText(model.model);
  await expect(page.getByTestId("chat-selected-model-key")).toHaveAttribute("data-model-key", model.key);
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByTestId("header-model-indicator")).toBeVisible();
    if (width < 640) {
      await expect.poll(() => page.locator("#mainContent").evaluate(element => element.getBoundingClientRect().left)).toBeLessThanOrEqual(1);
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    expect(overflow, `page horizontal overflow at ${width}px`).toBe(false);
    await page.screenshot({ path: test.info().outputPath(`chat-${width}.png`) });
  }
});

test("populated model inventory keeps actions and collapsed navigation usable", async ({ page, context, baseURL }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated QA server");
  expect(new URL(baseURL).hostname).toBe("127.0.0.1");
  const login = await context.request.post("/api/auth/login", { data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD } });
  expect(login.ok()).toBeTruthy();
  const models = Array.from({ length: 23 }, (_, index) => ({ key: `campaign-${index}`, name: `Campaign model ${index}`, model: `campaign-${index}.gguf`, provider: "llamacpp", runtime: "native-llamacpp", runtimeStatus: "stopped", role: "main", enabled: true }));
  await page.route("**/api/ui/bootstrap", async route => {
    const response = await route.fetch();
    const body = await response.json();
    const data = body.data || body;
    Object.assign(data, { models, tasks: [], security: { ...data.security, native: true, desktopOnly: true } });
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/model-registry", route => route.fulfill({ json: { ok: true, data: { models, providers: [] } } }));
  await page.addInitScript(() => {
    localStorage.setItem("rasputin-onboarded", "1");
    localStorage.setItem("rasputin-models-rail-collapsed", "0");
  });
  await page.setViewportSize({ width: 1427, height: 934 });
  await page.goto("/#chat");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  await page.getByTestId("nav-models").click();
  await page.locator("#models-tab-installed").click();
  const toolbar = page.locator(".models-inventory-toolbar");
  for (const name of ["Scan GGUF", "Refresh"]) {
    const button = toolbar.getByRole("button", { name, exact: true });
    await expect(button).toBeVisible();
    await button.click({ trial: true });
    expect(await button.evaluate(element => {
      const box = element.getBoundingClientRect();
      const parent = element.closest(".models-inventory-toolbar").getBoundingClientRect();
      return box.top >= parent.top && box.bottom <= parent.bottom + 1;
    })).toBe(true);
  }
  await page.getByTestId("models-rail-toggle").click();
  for (const tab of await page.locator("#models-navigation [role=tab]").all()) {
    await expect(tab.locator("svg")).toBeVisible();
    await tab.click({ trial: true });
  }
  await page.screenshot({ path: test.info().outputPath("models-collapsed-1427.png") });
  await page.getByTestId("models-rail-toggle").click();
  await page.locator("#models-tab-installed").focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.locator("#models-tab-running")).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("End");
  await expect(page.locator("#models-tab-settings")).toHaveAttribute("aria-selected", "true");
  const runtime = page.getByTestId("native-runtime-settings");
  await runtime.scrollIntoViewIfNeeded();
  await page.screenshot({ path: test.info().outputPath("models-advanced-1427.png") });
  expect(await runtime.evaluate(element => element.scrollHeight <= element.clientHeight + 1), "runtime description must not clip").toBe(true);
  for (const width of [1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator("#models-tab-installed").click();
    for (const name of ["Scan GGUF", "Refresh"]) {
      await toolbar.getByRole("button", { name, exact: true }).click({ trial: true });
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `model dialog page overflow at ${width}px`).toBe(true);
    await page.screenshot({ path: test.info().outputPath(`models-${width}.png`) });
  }
});
