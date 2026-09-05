import { expect, test } from "@playwright/test";

const repository = "unsloth/Qwen3.8-27B-GGUF";
const modelKey = "artifact-qwen38-q4km";

test("Discover loads a durable My Models artifact through provisional first-load placement", async ({ page }) => {
  const model = {
    key: modelKey,
    name: "Qwen3.8-27B-GGUF (Q4_K_M)",
    model: "Qwen3.8-27B-UD-Q4_K_M.gguf",
    repository,
    runtime: "native-llamacpp",
    provider: "llamacpp",
    managed: true,
    artifactAvailable: true,
    sizeBytes: 16464440224,
    hostModelPath: "C:/isolated/models/Qwen3.8-27B-UD-Q4_K_M.gguf",
    containerStatus: "stopped",
  };
  const hardware = {
    ok: true,
    status: "ready",
    detectedHardware: { gpus: [
      { index: 0, name: "GPU A", memoryTotalMb: 12288, memoryFreeMb: 11577 },
      { index: 1, name: "GPU B", memoryTotalMb: 16311, memoryFreeMb: 12391 },
    ] },
  };
  let startRequest = null;

  await page.route("**/api/ui/bootstrap", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const data = body.data || body;
    data.models = [model];
    data.modelCatalog = { items: [{
      id: repository,
      modelId: repository,
      name: "Qwen3.8 27B",
      source: "huggingface",
      purpose: "chat",
      capabilities: ["chat"],
      runtimeOptions: [{ protocolId: "llamaCppGgufServer", label: "llama.cpp" }],
      vramEstimateGb: 16,
    }], categories: [], runtimes: [] };
    await route.fulfill({ response, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.route("**/api/model-registry", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { models: [model], providers: [] }, error: null }),
  }));
  await page.route("**/api/model-catalog?fit=true", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { items: [{
      id: repository,
      modelId: repository,
      name: "Qwen3.8 27B",
      source: "huggingface",
      purpose: "chat",
      capabilities: ["chat"],
      runtimeOptions: [{ protocolId: "llamaCppGgufServer", label: "llama.cpp" }],
      vramEstimateGb: 16,
    }], categories: [], runtimes: [] }, error: null }),
  }));
  await page.route("**/api/model-catalog/search?**", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { items: [{ id: repository, modelId: repository, name: "Qwen3.8 27B", source: "huggingface", purpose: "chat", capabilities: ["chat"], vramEstimateGb: 16 }], count: 1 }, error: null }),
  }));
  await page.route("**/api/warsat/hardware?native_models=true", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: hardware, error: null }),
  }));
  await page.route("**/api/runtime/llamacpp/status", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: { state: "install_required" }, error: null }),
  }));
  await page.route("**/api/models/downloads", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: [], error: null }),
  }));
  await page.route("**/api/model-catalog/load-plan-preview", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data: {
      blocked: true,
      accepted: false,
      blockReasons: ["model requires 15600 MiB but no permitted GPU allocation fits"],
      resolvedSettings: { requiredMemoryMb: 15600 },
    }, error: null }),
  }));
  await page.route("**/api/model-registry/start", async (route) => {
    startRequest = route.request().postDataJSON();
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, data: { ok: true, status: "running" }, error: null }) });
  });

  await page.goto("/#discover");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  const onboarding = page.getByRole("dialog", { name: "Welcome to Rasputin" });
  if (await onboarding.isVisible()) await onboarding.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByRole("dialog", { name: "Discover Models" })).toBeVisible();
  const row = page.getByTestId("discover-model-row").filter({ hasText: "Qwen3.8 27B" });
  await expect(row).toContainText("In My Models");
  await row.getByRole("button", { name: "Load installed model Qwen3.8 27B" }).click();

  const dialog = page.getByRole("dialog", { name: /Qwen3\.8-27B-UD-Q4_K_M/ });
  await expect(dialog).toContainText("First-load placement check");
  const load = dialog.getByRole("button", { name: "Load model", exact: true });
  await expect(load).toBeEnabled();
  await load.click();
  await expect.poll(() => startRequest?.key).toBe(modelKey);
  expect(startRequest.profile.memoryMode).toBe("gpu_preferred");
  expect(startRequest.profile.splitMode).toBe("auto");
});
