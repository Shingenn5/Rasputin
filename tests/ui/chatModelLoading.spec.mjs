import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.beforeEach(async ({ context }) => {
  test.skip(!process.env.RASPUTIN_TEST_SESSION, "Requires an isolated authenticated test server");
  const session = JSON.parse(await readFile(process.env.RASPUTIN_TEST_SESSION, "utf8"));
  expect((await context.request.post("/api/auth/login", { data: { username: "admin", password: session.password } })).ok()).toBeTruthy();
  await context.request.post("/api/preferences", { data: { onboarded: true } });
});

for (const width of [1440, 390]) {
  test(`Chat can load a downloaded model and recover a duplicate connection at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const native = { key: "chat-native", name: "Downloaded Qwen", model: "Qwen-35B-Q4_K_M.gguf", runtime: "native-llamacpp", provider: "llamacpp", managed: true,
      artifactAvailable: true, hostModelPath: "C:/isolated/Qwen-35B-Q4_K_M.gguf", sizeMb: 4000, sizeBytes: 4194304000,
      runtimeStatus: "stopped", containerStatus: "stopped", contextWindow: 2048, contextDetectedAt: 1 };
    const connection = { key: "chat-connection", name: "Duplicate external Qwen", model: "Qwen-35B-Q4_K_M", runtime: "external-local", provider: "openai-compatible", managed: false, runtimeStatus: "unreachable" };
    const missing = { ...native, key: "missing-native", model: "missing.gguf", artifactAvailable: false };
    const models = [native, connection, missing];
    let start;
    const fulfill = (route, data) => route.fulfill({ json: { ok: true, data } });
    await page.route("**/api/ui/bootstrap", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      (body.data || body).models = models;
      await route.fulfill({ response, json: body });
    });
    await page.route("**/api/model-registry", (route) => fulfill(route, { models, providers: [] }));
    await page.route("**/api/warsat/hardware?native_models=true", (route) => fulfill(route, { devices: [{ id: "0", free_mb: 16000 }], safetyMarginMb: 512 }));
    await page.route("**/api/runtime/llamacpp/status", (route) => fulfill(route, { state: "ready", capabilities: {} }));
    await page.route("**/api/model-registry/start", (route) => {
      start = route.request().postDataJSON();
      native.runtimeStatus = native.containerStatus = "starting";
      return fulfill(route, { ok: true, status: "starting" });
    });
    await page.goto("/#chat");
    await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
    await page.getByTestId("chat-model-chip").click();
    const picker = page.getByTestId("model-side-panel");
    await expect(picker).toContainText("Load model");
    await expect(picker).not.toContainText("missing.gguf");
    await picker.getByRole("button", { name: /Qwen-35B-Q4_K_M/ }).click();
    const dialog = page.locator(".studio-load-modal");
    // The old 2K session allocation must not prevent a new 8K load.
    await expect(dialog.getByRole("button", { name: "Load model", exact: true })).toBeEnabled();
    await page.screenshot({ path: test.info().outputPath(`chat-load-${width}.png`) });
    await dialog.getByRole("button", { name: "Load model", exact: true }).click();
    await expect(dialog).not.toBeVisible();
    expect(start).toMatchObject({ key: native.key, background: true, profile: { contextLength: 8192 } });
    await page.getByTestId("system-status-trigger").click();
    await expect(page.getByTestId("hardware-monitor")).toContainText("Loading");
    native.runtimeStatus = "reachable";
    native.containerStatus = "running";
    await expect(page.getByTestId("hardware-monitor")).toContainText("Ready", { timeout: 10000 });
    await page.keyboard.press("Escape");
    native.runtimeStatus = native.containerStatus = "stopped";
    await page.goto("/#models");
    const row = page.locator('[data-model-key="chat-connection"]');
    await row.getByRole("button", { name: "Load local copy", exact: true }).click();
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Load model", exact: true }).click();
    await expect(dialog).not.toBeVisible();
    expect(start.key).toBe(native.key);
  });
}
