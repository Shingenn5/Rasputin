import { expect, test } from "@playwright/test";

const models = [
  { key: "loaded", model: "Local loaded model", managed: true, runtime: "native", runtimeStatus: "reachable", provider: "llamacpp", enabled: true },
  { key: "stopped", model: "Selected but stopped", runtime: "native", runtimeStatus: "stopped", provider: "llamacpp", enabled: true },
  { key: "remote", model: "Remote API model", runtime: "remote-api", runtimeStatus: "reachable", provider: "openai-compatible", enabled: true },
];

test("side popup shows running models and hardware, dismisses, and stays within the viewport", async ({ page, context }) => {
  test.setTimeout(60000);
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated server");
  const login = await context.request.post("/api/auth/login", { data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD } });
  expect(login.ok()).toBeTruthy();
  await page.route("**/api/ui/bootstrap", async route => {
    const response = await route.fetch();
    const json = await response.json();
    json.data.preferences = { ...json.data.preferences, onboarded: true, selectedModel: "stopped" };
    json.data.models = models;
    await route.fulfill({ json });
  });
  await page.route("**/api/model-registry", route => route.fulfill({ json: { ok: true, data: { models } } }));
  let liveUpdates = false;
  let metricsUnavailable = false;
  await page.route("**/api/settings", async route => {
    const response = await route.fetch();
    const json = await response.json();
    const data = json.data || json;
    data.hardware = { ...data.hardware, showLiveUsage: liveUpdates, refreshIntervalMs: 1000 };
    await route.fulfill({ json });
  });
  let metricRequests = 0;
  await page.route("**/api/warsat/system-metrics", route => {
    metricRequests += 1;
    if (metricsUnavailable) return route.fulfill({ status: 503, json: { ok: false, error: "Hardware telemetry unavailable" } });
    return route.fulfill({ json: { ok: true, data: {
      ram: { usedGb: 12, totalGb: 32 }, cpu: { percent: 27 },
      gpus: [{ index: 0, name: "Test GPU", memoryUsedMb: 4096, memoryTotalMb: 8192, utilization: 42 }],
    } } });
  });
  await page.goto("/#chat");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  const trigger = page.getByTestId("system-status-trigger");
  const popup = page.getByRole("dialog", { name: "System status", exact: true });
  await expect(trigger).toBeVisible();
  await expect(popup).toBeHidden();
  await expect(page.getByTestId("header-model-indicator")).toHaveCount(0);
  expect(metricRequests).toBe(0);

  for (const [width, height] of [[1440, 1000], [1024, 768], [375, 812], [812, 375]]) {
    await page.setViewportSize({ width, height });
    await trigger.focus();
    await page.keyboard.press("Enter");
    await expect(popup).toBeVisible();
    await expect(popup.getByTestId("system-status-model")).toHaveText("Local loaded modelReady");
    await expect(popup).not.toContainText("Selected but stopped");
    await expect(popup).not.toContainText("Remote API model");
    await expect(popup).toContainText("RAM 12.0 GB / 32.0 GB");
    await expect(popup).toContainText("CPU 27%");
    await expect(popup).toContainText("4.0 GB / 8.0 GB");
    const bounds = await popup.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(height);
    expect(await popup.evaluate(element => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: test.info().outputPath(`system-status-${width}.png`) });
    await page.keyboard.press("Escape");
    await expect(popup).toBeHidden();
    await expect(trigger).toBeFocused();
    await trigger.click();
    await popup.getByRole("button", { name: "Close system status" }).click();
    await expect(popup).toBeHidden();
    await trigger.click();
    await page.mouse.click(width - 15, 20);
    await expect(popup).toBeHidden();
  }

  // A runtime update must remove stopped models rather than retain the saved selection.
  models[0].runtimeStatus = "stopped";
  await page.evaluate(() => {
    localStorage.setItem("rasputin-theme", "rasputin-light");
    localStorage.setItem("rasputin-theme-explicit", "1");
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  liveUpdates = true;
  metricsUnavailable = true;
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "rasputin-light");
  await trigger.click();
  await expect(popup).toContainText("No model loaded");
  await expect(popup).toContainText("Hardware telemetry unavailable");
  metricsUnavailable = false;
  await expect(popup).toContainText("CPU 27%");
  await expect(popup).not.toContainText("Hardware telemetry unavailable");
  await page.screenshot({ path: test.info().outputPath("system-status-light.png") });
  await page.keyboard.press("Escape");
  const requestsAfterClose = metricRequests;
  await page.waitForTimeout(1200);
  expect(metricRequests).toBe(requestsAfterClose);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByTestId("chat-model-chip").click();
  await expect(page.getByRole("dialog", { name: "Select a model to load" })).toBeVisible();
});
