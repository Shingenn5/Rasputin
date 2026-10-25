import { expect, test } from "@playwright/test";
import { createServer } from "node:http";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import path from "node:path";

test.beforeEach(async ({ page, context }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated server");
  await context.request.post("/api/auth/login", { data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD } });
  await page.route("**/api/ui/bootstrap", async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    json.data.security = { ...json.data.security, native: true, desktopOnly: true };
    await route.fulfill({ json });
  });
  await page.goto("/#models");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  const welcome = page.getByRole("dialog", { name: "Welcome to Rasputin" });
  if (await welcome.isVisible()) await welcome.getByRole("button", { name: "Skip for now" }).click();
});

test("model workspace keeps all areas reachable across window sizes", async ({ page }) => {
  for (const [width, height] of [[1920, 1080], [1280, 720], [1024, 600], [800, 600], [390, 844], [900, 480]]) {
    await page.setViewportSize({ width, height });
    const dialog = page.getByRole("dialog", { name: "Models", exact: true });
    await expect(dialog).toBeVisible();
    for (const name of ["Discover", "My Models", "Loaded", "Advanced"]) {
      const tab = dialog.getByRole("tab", { name, exact: true });
      await tab.click();
      await expect(tab).toHaveAttribute("aria-selected", "true");
    }
    await dialog.getByRole("tab", { name: "My Models", exact: true }).click();
    await dialog.getByRole("button", { name: "Add existing model", exact: true }).click();
    await dialog.locator(".local-model-sources > summary").click();
    await expect(dialog.getByRole("button", { name: "Scan known model folders" })).toBeVisible();
    const bounds = await dialog.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.y).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(height + 1);
    const overflow = await dialog.evaluate((element) => element.scrollWidth - element.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await page.screenshot({ path: test.info().outputPath(`models-${width}-${height}.png`) });
    await dialog.getByRole("button", { name: "Add existing model", exact: true }).click();
  }
});

test("legacy Discover route opens the shared workspace with keyboard tab navigation", async ({ page }) => {
  await page.goto("/#discover");
  const dialog = page.getByRole("dialog", { name: "Models", exact: true });
  const discover = dialog.getByRole("tab", { name: "Discover", exact: true });
  await expect(discover).toHaveAttribute("aria-selected", "true");
  await discover.focus();
  await page.keyboard.press("ArrowRight");
  const library = dialog.getByRole("tab", { name: "My Models", exact: true });
  await expect(library).toBeFocused();
  await expect(library).toHaveAttribute("aria-selected", "true");
});

test("chat composer remains inside the window when resized", async ({ page }) => {
  await page.getByRole("dialog", { name: "Models", exact: true }).getByRole("button", { name: "Close dialog" }).click();
  for (const [width, height] of [[1920, 1080], [1280, 720], [1024, 600], [800, 600], [390, 844], [900, 480]]) {
    await page.setViewportSize({ width, height });
    const composer = page.locator("#objective");
    await expect(composer).toBeVisible();
    const bounds = await composer.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(height + 1);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  }
});

test("connect a local engine and apply saved inference controls to a real request", async ({ page, context }) => {
  let requestBody;
  let modelKey;
  const server = createServer(async (request, response) => {
    if (request.method === "GET") {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ data: [{ id: "integration-fixture" }] }));
      return;
    }
    let body = "";
    for await (const chunk of request) body += chunk;
    requestBody = JSON.parse(body);
    if (requestBody.stream) {
      response.writeHead(200, { "Content-Type": "text/event-stream" });
      response.end('data: {"choices":[{"delta":{"content":"Fixture response."},"finish_reason":null}]}\n\ndata: [DONE]\n\n');
    } else {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ choices: [{ message: { role: "assistant", content: "Fixture response." }, finish_reason: "stop" }] }));
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    await page.getByRole("button", { name: "Add existing model", exact: true }).click();
    const sources = page.getByTestId("local-model-sources");
    await sources.locator(":scope > summary").click();
    await sources.getByText("Connect a running local engine", { exact: true }).click();
    await sources.getByLabel("Local API address").fill(`http://127.0.0.1:${server.address().port}/v1`);
    await sources.getByRole("button", { name: "Find served models" }).click();
    await expect(sources.getByLabel("Served model")).toHaveValue("integration-fixture");
    await sources.getByRole("button", { name: "Connect model", exact: true }).click();
    await expect(sources).toContainText("Local engine model connected");
    await sources.locator(":scope > summary").click();
    const connected = (await (await context.request.get("/api/model-registry")).json()).data;
    modelKey = connected.models.find((item) => item.model === "integration-fixture" && item.baseUrl.endsWith(`:${server.address().port}/v1`)).key;
    await page.locator(`[data-model-key="${modelKey}"]`).click();
    const inspector = page.getByTestId("installed-model-inspector");
    await inspector.getByRole("tab", { name: "Response", exact: true }).click();
    await inspector.getByLabel("System prompt").fill("Use the saved fixture instruction.");
    await inspector.getByRole("slider", { name: "Temperature" }).fill("0.6");
    await inspector.getByLabel("Limit response length").check();
    await inspector.getByLabel("Maximum tokens").fill("256");
    await inspector.getByLabel("Stop strings").fill("END");
    const saved = page.waitForResponse((response) => response.url().endsWith("/api/model-registry/inference-profile") && response.request().method() === "POST");
    await inspector.getByRole("button", { name: "Save inference settings" }).click();
    expect((await saved).ok()).toBeTruthy();
    const registry = (await (await context.request.get("/api/model-registry")).json()).data;
    const model = registry.models.find((item) => item.model === "integration-fixture" && item.baseUrl.endsWith(`:${server.address().port}/v1`));
    expect(model.inferenceProfile.temperature).toBe(0.6);
    const taskResponse = await context.request.post("/api/tasks", { data: { objective: "Hello fixture", model: model.key, mode: "chat", memoryMode: "off", reasoning: "off" } });
    expect(taskResponse.ok()).toBeTruthy();
    await expect.poll(() => requestBody?.temperature).toBe(0.6);
    expect(requestBody.max_tokens).toBeLessThanOrEqual(256);
    expect(requestBody.stop).toEqual(["END"]);
    expect(JSON.stringify(requestBody.messages)).toContain("Use the saved fixture instruction.");
  } finally {
    if (modelKey) await context.request.post("/api/model-registry/delete", { data: { key: modelKey } });
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
});

test("import an exported GGUF and deploy with a selected load preset", async ({ page, context }) => {
  test.skip(!process.env.RASPUTIN_TEST_SCRATCH_DIR, "Requires an external session scratch folder");
  const folder = await mkdtemp(path.join(process.env.RASPUTIN_TEST_SCRATCH_DIR, "gguf-export-"));
  const file = path.join(folder, "export-fixture.gguf");
  await writeFile(file, "GGUFfixture");
  let modelKey;
  let start;
  try {
    await page.getByRole("button", { name: "Add existing model", exact: true }).click();
    const sources = page.getByTestId("local-model-sources");
    await sources.locator(":scope > summary").click();
    await sources.getByLabel("Model export folder").fill(folder);
    await sources.getByRole("button", { name: "Scan and import folder" }).click();
    await expect(sources).toContainText("1 models added");
    await sources.locator(":scope > summary").click();
    const registry = (await (await context.request.get("/api/model-registry")).json()).data;
    modelKey = registry.models.find((item) => item.model === "export-fixture.gguf").key;
    await page.locator(`[data-model-key="${modelKey}"]`).click();
    await page.route("**/api/model-catalog/load-plan-preview", (route) => route.fulfill({ json: { ok: true, data: { accepted: true, blocked: false, resolvedSettings: {} } } }));
    await page.route("**/api/model-registry/start", (route) => {
      start = route.request().postDataJSON();
      return route.fulfill({ json: { ok: true, data: { ok: true } } });
    });
    await page.getByTestId("installed-model-inspector").getByRole("button", { name: "Load Model", exact: true }).click();
    const load = page.getByRole("dialog", { name: "export-fixture.gguf", exact: true });
    await load.getByRole("button", { name: "CPU only", exact: true }).click();
    await load.getByRole("button", { name: "Load model", exact: true }).click();
    await expect.poll(() => start?.key).toBe(modelKey);
    expect(start.profile.memoryMode).toBe("cpu_only");
    expect(start.profile.gpuLayers).toBe(0);
  } finally {
    if (modelKey) await context.request.post("/api/model-registry/delete", { data: { key: modelKey } });
    await rm(folder, { recursive: true, force: true });
  }
});
