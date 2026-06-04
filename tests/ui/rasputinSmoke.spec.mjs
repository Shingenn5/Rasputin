import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";

const screenshotDir = "test-results/rasputin-screenshots";

test.beforeAll(() => {
  mkdirSync(screenshotDir, { recursive: true });
});

test.beforeEach(async ({ request }) => {
  await request.post("/api/workspace/select", {
    data: {
      path: ".",
    },
  });
  await request.post("/api/preferences", {
    data: {
      theme: "rasputin-light",
      sidebarCollapsed: false,
      selectedModel: "main-vllm",
      testingMode: false,
      skill: "general",
      taskMode: "chat",
      subagents: 0,
      activeView: "home",
      activeSettingsSection: "general",
    },
  });
});

async function waitForAppReady(page) {
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 15000 });
  await expect(page.locator("#workspacePill")).not.toContainText("loading", { timeout: 15000 });
  await expect(page.locator("#model")).toContainText("Main Local Model");
  await expect(page.locator("#selectedModelHealth")).not.toContainText("Checking selected model");
}

test("home shell settings and dry-run task work", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);
  await expect(page).toHaveTitle("Rasputin");

  await expect(page.locator("#homeView")).toBeVisible();
  await expect(page.locator("[data-testid='nav-home']")).toContainText("Home");
  await expect(page.locator("[data-testid='nav-models']")).toContainText("Models");
  await expect(page.locator("[data-testid='nav-activity']")).toContainText("Activity");
  await expect(page.locator("[data-testid='nav-warsat']")).toContainText("Warsat");
  await expect(page.locator("#workspacePill")).toContainText("Project Root");
  await expect(page.locator("#model")).not.toContainText("Dry Run");
  await expect(page.locator("#objective")).toBeVisible();
  await expect(page.locator("#selectedModelHealth")).toBeVisible();
  await expect(page.locator("#welcomePanel")).toBeAttached();
  await expect(page.locator("#welcomePanel")).toBeVisible();
  await expect(page.locator("#tasks")).not.toContainText("Testing the Rasputin live smoke harness.");

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("#settingsShell")).toBeVisible();
  await expect(page.locator("#settings-models")).toBeVisible();
  await expect(page.locator("[data-testid='active-model-card']")).toContainText("Main Local Model");
  await expect(page.locator("[data-testid='advanced-model-registry']")).toBeVisible();
  await expect(page.locator("[data-testid='gguf-scan']")).toBeVisible();
  await page.locator("[data-testid='advanced-model-registry'] summary").click();
  await expect(page.locator("#modelRegistry")).toContainText("Testing Mode");
  await page.locator("[data-testid='advanced-model-controls'] summary").click();
  await page.locator("[data-testid='testing-mode-toggle']").check();

  await page.locator("[data-testid='nav-home']").click();
  await expect(page.locator("#homeView")).toBeVisible();
  await page.locator("#model").selectOption("dry-run");
  await page.locator("#objective").fill("Testing the Rasputin UI harness.");
  await page.locator("#sendBtn").click();

  await expect(page.locator("#tasks")).toContainText("Testing the Rasputin UI harness.");
  await expect(page.locator("#tasks")).toContainText("done", { timeout: 15000 });

  await page.locator("[data-testid='runtime-details-toggle'] summary").first().click();
  await page.locator("[data-testid='activity-task-details']").first().click();
  await expect(page.locator("[data-testid='task-details-drawer']")).toBeVisible();
  await expect(page.locator("[data-testid='task-details-drawer']")).toContainText("Testing the Rasputin UI harness.");
  await expect(page.locator("[data-testid='task-details-overview']")).toBeVisible();
  await page.getByRole("tab", { name: "Logs" }).click();
  await expect(page.locator("[data-testid='task-details-logs']")).toBeVisible();
  await page.getByRole("tab", { name: "Artifacts" }).click();
  await expect(page.locator("[data-testid='task-details-artifacts']")).toBeVisible();
  await page.locator("[data-testid='task-details-close']").click();
  await expect(page.locator("[data-testid='task-details-drawer']")).toBeHidden();
});

test("sidebar collapse persists and themes switch", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await expect(page.locator("[data-testid='nav-workspaces']")).toContainText("Workspaces");
  await page.locator("[data-testid='sidebar-toggle']").click();
  await expect(page.locator("body")).toHaveClass(/sidebar-collapsed/);
  await page.reload();
  await waitForAppReady(page);
  await expect(page.locator("body")).toHaveClass(/sidebar-collapsed/);

  await page.locator("[data-testid='sidebar-toggle']").click();
  await expect(page.locator("body")).not.toHaveClass(/sidebar-collapsed/);

  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-appearance']").click();
  await page.locator("[data-testid='theme-select']").selectOption("rasputin-dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "rasputin-dark");
  await page.locator("[data-testid='theme-select']").selectOption("contrast");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "contrast");
  await page.reload();
  await waitForAppReady(page);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "contrast");
  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-appearance']").click();
  await page.locator("[data-testid='theme-select']").selectOption("rasputin-light");
});

test("key settings destinations are reachable", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("#workspacesView")).toBeVisible();
  await expect(page.locator("[data-testid='workspace-browser']")).toBeVisible();
  await expect(page.locator("#workspaceRootList")).not.toBeEmpty();
  await expect(page.locator("#workspaceEntries")).toBeVisible();
  await page.locator(".workspace-mount-panel summary").click();
  await page.locator("#workspaceMountForm #mountHostPath").fill("C:\\Users\\example\\Documents");
  await page.locator("#workspaceMountForm").evaluate(form => form.requestSubmit());
  await expect(page.locator("[data-testid='workspace-mount-plan']")).toContainText("Read-only");

  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-safety']").click();
  await expect(page.locator("#securityForm")).toBeVisible();

  await page.locator("[data-testid='settings-knowledge']").click();
  await expect(page.locator("#ragIngestForm")).toBeVisible();

  await page.locator("[data-testid='nav-activity']").click();
  await expect(page.locator("#activityView")).toBeVisible();
  await expect(page.locator("#taskCount")).toBeVisible();
});

test("activity hub groups runtime pages", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-activity']").click();
  await expect(page.locator("#activityView")).toBeVisible();
  await expect(page.locator("#activityView")).toContainText("Runs");
  await page.getByRole("tab", { name: "Approvals" }).click();
  await expect(page.locator("#activity-panel-approvals")).toBeVisible();
  await expect(page.locator("#activity-panel-approvals")).toContainText(/No approvals|Code/);
  await page.getByRole("tab", { name: "Sessions" }).click();
  await expect(page.locator("#activityView")).toContainText(/Sessions|No sessions/);
  await page.getByRole("tab", { name: "Pipeline" }).click();
  await expect(page.locator("#activityView")).toContainText("Agent Runtime Pipeline");
  await page.getByRole("tab", { name: "Audit" }).click();
  await expect(page.locator("#activityAuditLog")).toBeVisible();
});

test("warsat recipes produce dry-run launch plans", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-warsat']").click();
  await expect(page.locator("[data-testid='warsat-view']")).toBeVisible();
  await expect(page.locator("[data-testid='warsat-recipe-card']")).toHaveCount(2);
  await expect(page.locator("[data-testid='warsat-view']")).toContainText("Plan only");
  await page.locator("#warsatRecipeId").selectOption("vllmCudaOpenai");
  await page.locator("#warsatModelRef").fill("Qwen/Qwen2.5-Coder-7B-Instruct");
  await page.locator("#warsatHostPort").fill("8020");
  await page.locator("#warsatRole").selectOption("coder");
  await page.locator("[data-testid='warsat-plan-form']").evaluate(form => form.requestSubmit());
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toBeVisible();
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("vLLM CUDA OpenAI Server");
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("localhost only");
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("127.0.0.1:8020:8000");
});

test("visual review screenshots", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);
  await page.locator("[data-testid='nav-home']").click();

  await page.screenshot({ path: `${screenshotDir}/home-desktop.png`, fullPage: true });

  await page.locator("[data-testid='sidebar-toggle']").click();
  await page.screenshot({ path: `${screenshotDir}/sidebar-collapsed.png`, fullPage: true });
  await page.locator("[data-testid='sidebar-toggle']").click();

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("#settings-models")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/settings-models.png`, fullPage: true });

  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("[data-testid='workspace-browser']")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/workspaces.png`, fullPage: true });

  await page.locator("[data-testid='nav-warsat']").click();
  await expect(page.locator("[data-testid='warsat-view']")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/warsat.png`, fullPage: true });

  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-appearance']").click();
  await page.locator("[data-testid='theme-select']").selectOption("rasputin-dark");
  await page.screenshot({ path: `${screenshotDir}/dark-theme.png`, fullPage: true });

  await page.locator("[data-testid='theme-select']").selectOption("rasputin-light");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("[data-testid='mobile-sidebar-toggle']").click();
  await page.locator("[data-testid='nav-home']").click();
  await page.screenshot({ path: `${screenshotDir}/home-mobile.png`, fullPage: true });
});
