import { expect, test } from "@playwright/test";

test("WarSat Advisor explains fit before creating an approval-gated plan", async ({ page, request }) => {
  if (process.env.RASPUTIN_TEST_PASSWORD) {
    const login = await request.post("/api/auth/login", {
      data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
    });
    expect((await login.json()).ok).toBe(true);
    const state = await request.storageState();
    await page.context().addCookies(state.cookies);
  }

  let planRequest = null;
  await page.route("**/api/model-catalog?fit=true", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          items: [{
            id: "Qwen/Qwen2.5-Coder-7B-Instruct",
            modelId: "Qwen/Qwen2.5-Coder-7B-Instruct",
            name: "Qwen Coder",
            purpose: "coding",
            capabilities: ["coding", "tools"],
            deployable: true,
            recommendedProtocol: "vllmCudaOpenai",
            toolCallParserHint: "hermes",
            contextWindow: 16384,
            vramEstimateGb: 12,
            fitLabel: "Strong fit",
          }],
          categories: [],
          runtimes: [],
        },
        error: null,
      }),
    });
  });
  await page.route("**/api/warsat/advisor", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.model.modelId).toBeTruthy();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          status: "ready_with_assumptions",
          planSeed: { protocolId: "vllmCudaOpenai", toolCallParser: "hermes", multiGpu: false },
          evidence: {
            confidence: "medium",
            observed: { aggregateVramGb: 28, gpus: [{}, {}] },
            estimated: { modelVramGb: 12, vramMarginGb: 16 },
          },
          blockers: [],
          warnings: [],
          assumptions: ["Largest fitting single GPU is the safe default; runtime sharding must be verified."],
          approvalBypassed: false,
        },
        error: null,
      }),
    });
  });
  await page.route("**/api/warsat/plan", async (route) => {
    planRequest = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          planId: "plan_advisor_test",
          protocolId: planRequest.protocolId,
          modelRef: planRequest.modelRef,
          phase: "planned",
          warnings: [],
          executionEnabled: false,
          dockerControlEnabled: false,
          dockerCliAvailable: true,
          approvalGranted: false,
        },
        error: null,
      }),
    });
  });

  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  await page.locator("[data-testid='nav-warsat']").click();
  await page.getByRole("button", { name: "Deploy" }).click();
  await page.locator("[data-testid='warsat-advisor']").getByRole("button", { name: "Analyze fit" }).click();

  const result = page.locator("[data-testid='warsat-advisor-result']");
  await expect(result).toContainText("28 GB VRAM");
  await expect(result).toContainText("12 GB demand");
  await expect(result).toContainText("Runtime sharding must be verified.");

  await page.getByRole("button", { name: "Create approval-gated plan" }).click();
  await expect.poll(() => planRequest?.toolCallParser).toBe("hermes");
  await expect(page.getByText("Deploy locked")).toBeVisible();
});
