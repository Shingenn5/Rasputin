import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.beforeEach(async ({ context }) => {
  test.skip(!process.env.RASPUTIN_TEST_SESSION, "Requires an isolated authenticated test server");
  const session = JSON.parse(await readFile(process.env.RASPUTIN_TEST_SESSION, "utf8"));
  const login = await context.request.post("/api/auth/login", { data: { username: "admin", password: session.password } });
  expect(login.ok()).toBeTruthy();
  await context.request.post("/api/preferences", { data: { onboarded: true } });
});

async function fixture(page) {
  const model = { key: "load-fixture", name: "Background test model", model: "background-test.gguf", provider: "llamacpp", runtime: "native-llamacpp", managed: true,
    artifactAvailable: true, hostModelPath: "C:/isolated/background-test.gguf", containerStatus: "stopped", runtimeStatus: "stopped" };
  const state = { requests: [], model };
  const fulfill = (route, data) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, data }) });
  await page.route("**/api/ui/bootstrap", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    (body.data || body).models = [model];
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/model-registry", (route) => fulfill(route, { models: [model], providers: [] }));
  await page.route("**/api/model-registry/start", (route) => {
    state.requests.push(route.request().postDataJSON());
    Object.assign(model, { containerStatus: "starting", runtimeStatus: "starting", loadStatus: { status: "loading", startedAt: Date.now() / 1000 } });
    return fulfill(route, { ok: true, status: "starting" });
  });
  await page.route("**/api/model-registry/stop", (route) => {
    Object.assign(model, { containerStatus: "stopped", runtimeStatus: "stopped" });
    delete model.loadStatus;
    return fulfill(route, { ok: true, status: "stopped" });
  });
  await page.route("**/api/model-catalog/load-plan-preview", (route) => fulfill(route, { accepted: true, blocked: false, resolvedSettings: { requiredMemoryMb: 1024 } }));
  await page.route("**/api/runtime/llamacpp/status", (route) => fulfill(route, { state: "ready" }));
  await page.route("**/api/warsat/system-metrics", (route) => fulfill(route, { ram: { usedGb: 4, totalGb: 32 }, cpu: { percent: 12 }, gpus: [] }));
  return state;
}

for (const width of [1440, 1024, 390]) {
  test(`background model loading, context presets, and movable gauge popup at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 });
    const state = await fixture(page);
    await page.goto("/#models");
    await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
    const inspector = page.getByTestId("installed-model-inspector");
    await inspector.getByRole("button", { name: "Load Model", exact: true }).click();
    const load = page.locator(".studio-load-modal");
    await load.getByLabel("Context length preset").selectOption("16384");
    await expect(load.getByLabel("Context length preset")).toHaveValue("16384");
    await load.getByLabel("Context length preset").selectOption("custom");
    await load.getByLabel("Custom context length", { exact: true }).fill("12288");
    await load.getByRole("button", { name: "Load model", exact: true }).click();
    await expect(load).not.toBeVisible();
    expect(state.requests[0]).toMatchObject({ key: "load-fixture", background: true, profile: { contextLength: 12288 } });
    await expect(inspector.getByRole("button", { name: "Cancel loading" })).toBeVisible();
    // Close the Models modal, then reload Chat while the same backend load remains active.
    await page.keyboard.press("Escape");
    await page.goto("/#chat");
    await page.reload();
    await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
    await page.getByTestId("system-status-trigger").click();
    const monitor = page.getByTestId("hardware-monitor");
    await expect(monitor.getByTestId("system-status-model")).toContainText("Loading");
    await expect(monitor).not.toContainText("No model loaded");
    const handle = monitor.getByRole("button", { name: "Move system status", exact: true });
    const before = await monitor.boundingBox();
    await handle.focus();
    await page.keyboard.press("ArrowDown");
    await expect.poll(async () => (await monitor.boundingBox()).y).toBe(before.y + 24);
    const grip = await handle.boundingBox();
    await page.mouse.move(grip.x + 12, grip.y + 12);
    await page.mouse.down();
    await page.mouse.move(grip.x + 12, grip.y + 52, { steps: 5 });
    await page.mouse.up();
    await expect.poll(async () => (await monitor.boundingBox()).y).toBe(before.y + 64);
    const moved = await monitor.boundingBox();
    await monitor.getByRole("button", { name: "Expand system status", exact: true }).click();
    await expect(monitor.getByRole("button", { name: "Restore system status size" })).toHaveAttribute("aria-expanded", "true");
    const expanded = await monitor.boundingBox();
    expect(expanded.width).toBeLessThanOrEqual(width - 16);
    await page.screenshot({ path: test.info().outputPath(`expanded-${width}.png`) });
    await monitor.getByRole("button", { name: "Restore system status size" }).click();
    await expect.poll(async () => (await monitor.boundingBox()).y).toBe(moved.y);
    Object.assign(state.model, { containerStatus: "running", runtimeStatus: "reachable" });
    delete state.model.loadStatus;
    await expect(monitor.getByTestId("system-status-model")).toContainText("Ready", { timeout: 8000 });
    await expect(monitor.getByTestId("system-status-model")).not.toContainText("Loading");
    const bounds = await monitor.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    if (width === 1440) {
      Object.assign(state.model, { containerStatus: "starting", runtimeStatus: "starting", loadStatus: { status: "loading" } });
      await page.reload();
      await page.getByTestId("system-status-trigger").click();
      await expect(monitor.getByTestId("system-status-model")).toContainText("Loading");
      await expect.poll(async () => (await monitor.boundingBox()).y).toBe(moved.y);
      Object.assign(state.model, { containerStatus: "stopped", runtimeStatus: "stopped", lastLoadFailure: { message: "Not enough memory. Choose a smaller context." } });
      delete state.model.loadStatus;
      await expect(monitor).toContainText("Couldn't load", { timeout: 8000 });
      await expect(monitor.getByRole("alert")).toContainText("Choose a smaller context");
    }
    await monitor.getByRole("button", { name: "Reset system status position" }).click();
    await page.keyboard.press("Escape");
    await expect(monitor).not.toBeVisible();
  });
}
