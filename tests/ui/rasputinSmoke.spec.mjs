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
      modeModelOverrides: {},
      subagents: 0,
      workspaceExplorer: {},
      activeView: "home",
      activeSettingsSection: "general",
      activeChatFolder: "all",
    },
  });
});

async function waitForAppReady(page) {
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 15000 });
  await expect(page.locator("#workspacePill")).not.toContainText("loading", { timeout: 15000 });
  await expect(page.locator("#model")).not.toContainText("Main Local Model");
  await expect(page.locator("#selectedModelHealth")).not.toContainText("Checking selected model");
}

async function openShellView(page, testId) {
  const isMobile = await page.evaluate(() => window.matchMedia("(max-width: 760px)").matches);
  if (isMobile) {
    await page.locator("[data-testid='mobile-sidebar-toggle']").click();
  }
  await page.locator(`[data-testid='${testId}']`).click();
  await expect(page.locator("body")).not.toHaveClass(/mobile-sidebar-open/);
}

async function assertNoShellOverflow(page, label) {
  const metrics = await page.evaluate((viewLabel) => {
    const activeView = document.querySelector(".app-view.active");
    const candidates = [
      document.documentElement,
      document.body,
      document.querySelector(".app-frame"),
      document.querySelector(".app-main"),
      activeView,
      activeView?.querySelector(".page-header"),
      activeView?.querySelector(".home-commandbar"),
      activeView?.querySelector(".chat-shell"),
      activeView?.querySelector(".workspace-layout"),
      activeView?.querySelector(".task-dashboard"),
      activeView?.querySelector(".activity-panel"),
      activeView?.querySelector(".models-content"),
      activeView?.querySelector(".settings-layout"),
      activeView?.querySelector(".settings-panels"),
      activeView?.querySelector(".warsat-dashboard"),
    ].filter(Boolean);
    return {
      label: viewLabel,
      viewport: window.innerWidth,
      documentOverflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth,
      offenders: candidates
        .map((node) => ({
          selector: node.id ? `#${node.id}` : node.className || node.tagName,
          scrollWidth: Math.round(node.scrollWidth),
          clientWidth: Math.round(node.clientWidth),
          overflow: Math.round(node.scrollWidth - node.clientWidth),
        }))
        .filter((item) => item.overflow > 2),
    };
  }, label);
  expect(metrics.documentOverflow, `${label} document overflow ${JSON.stringify(metrics)}`).toBeLessThanOrEqual(2);
  expect(metrics.offenders, `${label} overflowing shell nodes`).toEqual([]);
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
  await expect(page.locator("[data-testid='chat-mode-chip']")).toContainText("Chat");
  await page.locator("[data-testid='chat-mode-chip']").click();
  await expect(page.locator("[data-testid='mode-side-panel']")).toBeVisible();
  await expect(page.locator("[data-testid='mode-option']")).toHaveCount(6);
  await page.locator("[data-testid='mode-option']").filter({ hasText: "Code" }).getByRole("button", { name: /Code/ }).click();
  await expect(page.locator("[data-testid='chat-mode-chip']")).toContainText("Code");
  await expect(page.locator("#objective")).toBeVisible();
  await expect(page.locator("#selectedModelHealth")).toBeVisible();
  await expect(page.locator("#welcomePanel")).toBeAttached();
  await expect(page.locator("#welcomePanel")).toBeVisible();
  await expect(page.locator("#tasks")).not.toContainText("Testing the Rasputin live smoke harness.");

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("#modelsView")).toBeVisible();
  await expect(page.locator("[data-testid='active-model-card']")).not.toContainText("Main Local Model");
  await expect(page.locator("#models-active-card")).toBeVisible();
  await expect(page.locator("[data-testid='models-dev-catalog']")).toBeVisible();
  await expect(page.locator("[data-testid='catalog-model-card']").first()).toBeVisible();
  await expect(page.locator("[data-testid='catalog-send-to-warsat']")).toBeVisible();
  await expect(page.locator("#modelsView")).toContainText("Warsat Deployment Plan");
  await expect(page.locator("[data-testid='advanced-model-registry']")).toBeVisible();
  await expect(page.locator("[data-testid='gguf-scan']")).toBeVisible();
  await page.locator("[data-testid='advanced-model-registry'] summary").click();
  await expect(page.locator("#modelRegistry")).toContainText("Testing Mode");
  await page.locator("[data-testid='testing-mode-toggle']").check();

  await page.locator("[data-testid='nav-home']").click();
  await expect(page.locator("#homeView")).toBeVisible();
  await page.locator("[data-testid='active-model-chip']").click();
  await expect(page.locator("[data-testid='model-side-panel']")).toBeVisible();
  await page.locator("[data-testid='model-option']").filter({ hasText: "Testing Mode" }).click();
  await expect(page.locator("[data-testid='model-side-panel']")).toBeHidden();
  await expect(page.locator("#model")).toContainText("Testing Mode");
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
  await page.getByRole("tab", { name: "Outputs" }).click();
  await expect(page.locator("[data-testid='task-details-outputs']")).toBeVisible();
  await page.locator("[data-testid='task-details-close']").click();
  await expect(page.locator("[data-testid='task-details-drawer']")).toBeHidden();
});

test("sidebar collapse persists and themes switch", async ({ page }) => {
  test.setTimeout(60000);
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
  await page.locator("[data-testid='theme-select']").selectOption("bootswatch-slate");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "bootswatch-slate");
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
  await expect(page.locator("[data-testid='workspace-knowledge-panel']")).toBeVisible();
  await expect(page.locator("#workspaceRootList")).not.toBeEmpty();
  await expect(page.locator("#workspaceEntries")).toBeVisible();
  await expect(page.locator("[data-testid='workspace-root-card']").first()).toBeVisible();
  await expect(page.locator("[data-testid='workspace-file-row']").first()).toBeVisible();
  const previewRow = page.locator("[data-testid='workspace-file-row']").filter({ hasText: "requirements.txt" }).first();
  await expect(previewRow).toBeVisible();
  await previewRow.getByRole("button", { name: /requirements\.txt/ }).click();
  await expect(page.locator("[data-testid='workspace-preview-panel']")).toContainText("requirements.txt");
  await expect(page.locator("[data-testid='workspace-preview-panel']")).toContainText("fastapi");
  await page.locator("[data-testid='workspace-knowledge-panel']").getByRole("button", { name: "Refresh stats" }).click();
  await expect(page.locator("[data-testid='workspace-knowledge-panel']")).toContainText("Docs");
  await page.locator(".workspace-mount-panel summary").click();
  await page.locator("#workspaceMountForm #mountHostPath").fill("C:\\Users\\example\\Documents");
  await page.locator("#workspaceMountForm").evaluate(form => form.requestSubmit());
  await expect(page.locator("[data-testid='workspace-mount-plan']")).toContainText("Read-only");

  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-safety']").click();
  await expect(page.locator("#securityForm")).toBeVisible();
  await expect(page.locator("[data-testid='save-safety']")).toBeDisabled();
  await page.getByLabel("Docker control").check();
  await expect(page.locator("#securityForm")).toContainText("Unsaved safety changes");
  await expect(page.locator("[data-testid='save-safety']")).toBeEnabled();
  await page.locator("#securityForm").getByRole("button", { name: "Reset" }).click();
  await expect(page.locator("[data-testid='save-safety']")).toBeDisabled();

  await page.locator("[data-testid='settings-output']").click();
  await expect(page.locator("[data-testid='output-settings-form']")).toBeVisible();
  await page.locator("#markdownFolder").fill("workspace/ui-output-smoke");
  await page.locator("[data-testid='output-settings-form']").getByRole("button", { name: /Save Output/ }).click();
  await expect(page.locator("#settings-output")).toContainText("Output folder saved");

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

test("workspaces adapt to split-screen width", async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 760 });
  await page.goto("/");
  await waitForAppReady(page);
  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("[data-testid='workspace-browser']")).toBeVisible();

  const metrics = await page.locator(".workspace-layout").evaluate((layout) => {
    const box = (selector) => {
      const node = document.querySelector(selector);
      const rect = node.getBoundingClientRect();
      return {
        top: rect.top,
        bottom: rect.bottom,
        width: rect.width,
      };
    };
    const style = window.getComputedStyle(layout);
    return {
      areas: style.gridTemplateAreas,
      overflowX: layout.scrollWidth - layout.clientWidth,
      main: box(".workspace-main"),
      preview: box(".workspace-preview-panel"),
    };
  });

  expect(metrics.areas).toContain("workspace-preview workspace-preview");
  expect(metrics.main.width).toBeGreaterThanOrEqual(420);
  expect(metrics.preview.width).toBeGreaterThanOrEqual(760);
  expect(metrics.preview.top).toBeGreaterThan(metrics.main.top);
  expect(metrics.overflowX).toBeLessThanOrEqual(2);
});

test("primary views stay responsive across desktop split tablet and mobile", async ({ page }) => {
  test.setTimeout(90000);
  const viewports = [
    ["desktop", { width: 1440, height: 900 }],
    ["split", { width: 1180, height: 760 }],
    ["tablet", { width: 820, height: 900 }],
    ["mobile", { width: 390, height: 844 }],
  ];
  const views = [
    ["home", "nav-home", "#homeView"],
    ["workspaces", "nav-workspaces", "#workspacesView"],
    ["activity", "nav-activity", "#activityView"],
    ["models", "nav-models", "#modelsView"],
    ["warsat", "nav-warsat", "[data-testid='warsat-view']"],
    ["settings", "nav-settings", "#settingsShell"],
  ];

  for (const [viewportName, viewport] of viewports) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await waitForAppReady(page);

    for (const [viewName, navTestId, visibleSelector] of views) {
      await openShellView(page, navTestId);
      await expect(page.locator(visibleSelector)).toBeVisible();
      await assertNoShellOverflow(page, `${viewportName}:${viewName}`);
    }

    await openShellView(page, "nav-settings");
    await page.locator("[data-testid='settings-knowledge']").click();
    await expect(page.locator("#settings-knowledge")).toBeVisible();
    await assertNoShellOverflow(page, `${viewportName}:settings-knowledge`);
  }
});

test("chat sessions can be categorized into folders", async ({ page, request }) => {
  test.setTimeout(60000);
  const base = `Folder smoke chat ${Date.now()}`;
  const titles = Array.from({ length: 18 }, (_, index) => `${base} ${index + 1}`);
  const folderName = `UI Folder Smoke ${Date.now()}`;
  for (const title of titles) {
    await request.post("/api/tasks", {
      data: {
        objective: title,
        model: "dry-run",
        skill: "general",
        mode: "chat",
        workspacePath: ".",
      },
    });
  }

  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='sidebar-session-search']").fill(base);
  await page.locator("[data-testid='sidebar-session-sort']").selectOption("az");
  const smokeRows = page.locator("[data-testid='sidebar-session-row']").filter({ hasText: base });
  await expect(smokeRows).toHaveCount(18);
  await expect(smokeRows.first()).toContainText(titles[0]);
  await expect.poll(async () => {
    return page.locator("[data-testid='sidebar-session-list']").evaluate((node) => {
      const style = window.getComputedStyle(node);
      return style.overflowY === "scroll" && node.scrollHeight > node.clientHeight;
    });
  }).toBe(true);
  const listHeight = await page.locator("[data-testid='sidebar-session-list']").evaluate((node) => node.clientHeight);
  expect(listHeight).toBeGreaterThanOrEqual(220);

  await page.locator("[data-testid='sidebar-folder-create-toggle']").click();
  await page.locator("[data-testid='sidebar-folder-create'] input").fill(folderName);
  await page.locator("[data-testid='sidebar-folder-create']").getByRole("button", { name: /Create chat folder/i }).click();
  await expect(page.locator("[data-testid='sidebar-folder-filter']")).toContainText(folderName);

  const targetRow = page.locator("[data-testid='sidebar-session-row']").filter({ hasText: titles[17] });
  await targetRow.locator("[data-testid='sidebar-session-folder']").selectOption(folderName);
  await page.locator("[data-testid='sidebar-folder-filter']").selectOption(folderName);
  await expect(page.locator("[data-testid='sidebar-session-list']")).toContainText(titles[17]);
});

test("warsat protocols produce dry-run launch plans", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("[data-testid='models-dev-catalog']")).toBeVisible();
  await page.locator("[data-testid='catalog-model-card']").filter({ hasText: "Qwen2.5 Coder" }).click();
  await page.locator("[data-testid='catalog-send-to-warsat']").click();
  await expect(page.locator("[data-testid='warsat-view']")).toBeVisible();
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("Qwen/Qwen2.5-Coder-7B-Instruct");
  await page.locator("[data-testid='warsat-view']").getByRole("button", { name: "Clear plan" }).click();

  await page.locator("[data-testid='nav-warsat']").click();
  await expect(page.locator("[data-testid='warsat-view']")).toBeVisible();
  await expect(page.locator("[data-testid='warsat-view']")).toContainText("Ollama");
  expect(await page.locator("[data-testid='warsat-protocol-card']").count()).toBeGreaterThanOrEqual(3);
  await expect(page.locator("[data-testid='warsat-view']")).toContainText("Plan only");
  await page.locator("#warsatProtocolId").selectOption("vllmCudaOpenai");
  await page.locator("#warsatModelRef").fill("Qwen/Qwen2.5-Coder-7B-Instruct");
  await page.locator("#warsatHostPort").fill("8020");
  await page.locator("#warsatRole").selectOption("coder");
  await page.locator("#warsatStrengthProfile").selectOption("large");
  await page.locator("#warsatMaxModelLen").fill("12288");
  await page.locator("#warsatGpuMemoryUtilization").fill("0.84");
  await page.locator("#warsatTensorParallelSize").fill("2");
  await page.locator("#warsatQuantization").selectOption("awq");
  await page.locator("#warsatMemoryLimitGb").fill("24");
  await page.locator("#warsatShmSizeGb").fill("8");
  await page.locator("#warsatGpuDevice").fill("0");
  await page.locator("[data-testid='warsat-plan-form']").evaluate(form => form.requestSubmit());
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toBeVisible();
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("vLLM CUDA OpenAI Server");
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("Tuning And Limits");
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("localhost only");
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("127.0.0.1:8020:8000");
  await expect(page.locator("[data-testid='warsat-compose-preview']")).toContainText("services:");
  await expect(page.locator("[data-testid='warsat-compose-preview']")).toContainText("--max-model-len");
  await expect(page.locator("[data-testid='warsat-compose-preview']")).toContainText("--quantization");
  await expect(page.locator("[data-testid='warsat-compose-preview']")).toContainText("mem_limit");
  await expect(page.locator("[data-testid='warsat-compose-preview']")).toContainText("NVIDIA_VISIBLE_DEVICES");
  await page.locator("[data-testid='warsat-view']").getByRole("button", { name: "Clear plan" }).click();
  await page.locator("#warsatProtocolId").selectOption("llamaCppGgufServer");
  await page.locator("#warsatModelPath").fill("models/tiny-helper.gguf");
  await page.locator("#warsatHostPort").fill("8091");
  await page.locator("#warsatStrengthProfile").selectOption("small");
  await page.locator("[data-testid='warsat-plan-form']").evaluate(form => form.requestSubmit());
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("llama.cpp GGUF Server");
  await expect(page.locator("[data-testid='warsat-compose-preview']")).toContainText("/models/tiny-helper.gguf");
});

test("visual review screenshots", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);
  await page.locator("[data-testid='nav-home']").click();

  await page.locator("[data-testid='chat-mode-chip']").click();
  await expect(page.locator("[data-testid='mode-side-panel']")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/mode-panel.png`, fullPage: true });
  await page.keyboard.press("Escape");

  await page.screenshot({ path: `${screenshotDir}/home-desktop.png`, fullPage: true });

  await page.locator("[data-testid='sidebar-toggle']").click();
  await page.screenshot({ path: `${screenshotDir}/sidebar-collapsed.png`, fullPage: true });
  await page.locator("[data-testid='sidebar-toggle']").click();

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("#modelsView")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/models.png`, fullPage: true });

  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("[data-testid='workspace-browser']")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/workspaces.png`, fullPage: true });

  await page.locator("[data-testid='nav-activity']").click();
  await expect(page.locator("#activityView")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/activity.png`, fullPage: true });

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
