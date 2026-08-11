import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";

const screenshotDir = "test-results/rasputin-screenshots";

test.describe.configure({ timeout: 90000, mode: "serial" });

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
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  await expect(page.locator("#rasputinLoader")).toBeHidden({ timeout: 60000 });
  if (await page.locator("#workspacePill").count()) {
    await expect(page.locator("#workspacePill")).not.toContainText("loading", { timeout: 15000 });
  }
  if (await page.locator("#model").count()) {
    await expect(page.locator("#model")).not.toContainText("Main Local Model");
  }
  if (await page.locator("#selectedModelHealth").count()) {
    await expect(page.locator("#selectedModelHealth")).not.toContainText("Checking selected model");
  }
}

async function openShellView(page, testId) {
  const isMobile = await page.evaluate(() => window.matchMedia("(max-width: 760px)").matches);
  if (isMobile) {
    await page.locator("[data-testid='mobile-sidebar-toggle']").click();
  }
  await page.locator(`[data-testid='${testId}']`).click();
  await expect.poll(async () => {
    return ((await page.locator("body").getAttribute("class")) || "").includes("mobile-sidebar-open");
  }).toBe(false);
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
      activeView?.querySelector(".archive-layout"),
      activeView?.querySelector(".trials-layout"),
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

async function assertVisibleButtonsAreNamed(page, label) {
  const unnamed = await page.evaluate(() => {
    const visible = (node) => {
      const rect = node.getBoundingClientRect();
      const style = window.getComputedStyle(node);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    };
    return Array.from(document.querySelectorAll("button"))
      .filter(visible)
      .map((button) => ({
        id: button.id || "",
        testId: button.getAttribute("data-testid") || "",
        className: button.className || "",
        text: (button.textContent || "").replace(/\s+/g, " ").trim(),
        label: button.getAttribute("aria-label") || button.getAttribute("title") || "",
      }))
      .filter((button) => !button.text && !button.label);
  });
  expect(unnamed, `${label} unnamed visible buttons`).toEqual([]);
}

test("home shell settings and dry-run task work", async ({ page, request }) => {
  await page.goto("/");
  await waitForAppReady(page);
  await expect(page).toHaveTitle("Rasputin");

  await expect(page.locator("#homeView")).toBeVisible();
  await expect(page.locator("[data-testid='nav-home']")).toContainText("Dashboard");
  await expect(page.locator("[data-testid='nav-models']")).toContainText("Models");
  await expect(page.locator("[data-testid='nav-activity']")).toContainText("Activity");
  await expect(page.locator("[data-testid='nav-warsat']")).toContainText("Warsat");
  await expect(page.locator("[data-testid='work-mode-switcher']")).toBeVisible();
  await page.locator("[data-testid='dashboard-open-workstation']").click();
  await expect(page.locator("#chatView")).toBeVisible();
  await expect(page.locator("[data-testid='chat-mode-chip']")).toContainText("Chat");
  await page.locator("[data-testid='chat-mode-chip']").click();
  await expect(page.locator("[data-testid='command-menu']")).toBeVisible();
  await page.locator("[data-testid='command-item']").filter({ hasText: "Code" }).click();
  await expect(page.locator("[data-testid='chat-mode-chip']")).toContainText("Code");
  // A dry-run model is intentionally chat-only; verify the mode switcher
  // exposes Code without attempting an unsupported agentic send.
  await page.locator("[data-testid='chat-mode-chip']").click();
  await page.locator("[data-testid='command-item']").filter({ hasText: "Chat" }).click();
  await expect(page.locator("[data-testid='chat-mode-chip']")).toContainText("Chat");
  await expect(page.locator("#objective")).toBeVisible();
  await expect(page.locator("[data-testid='header-model-indicator']")).toBeVisible();
  await expect(page.locator("#taskForm")).toBeVisible();
  const sessionsBefore = await request.get("/api/sessions");
  const sessionsBeforeBody = await sessionsBefore.json();
  const sessionIdsBefore = new Set((sessionsBeforeBody.data?.sessions || []).map((session) => session.id));
  await page.locator("[data-testid='new-task']").click();
  await expect(page.locator(".ras-toast__message")).toContainText("New chat created");
  const sessionsResponse = await request.get("/api/sessions");
  const sessionsBody = await sessionsResponse.json();
  expect(sessionsBody.ok).toBe(true);
  expect(sessionsBody.data.sessions.some((session) => !sessionIdsBefore.has(session.id))).toBe(true);

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("#modelsView")).toBeVisible();
  await expect(page.locator("#models-tab-library")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("[data-testid='model-vram-filter']")).toBeVisible();
  await expect(page.locator("[data-testid='model-vram-filter']")).toContainText("Detected sharded pool");
  await expect(page.locator("#modelsView")).toContainText("Quick Start");
  await expect(page.locator("#models-panel-library")).toContainText(/locally cached model/);

  await page.getByRole("tab", { name: "Installed" }).click();
  await expect(page.locator("#models-panel-installed")).toBeVisible();
  await expect(page.locator("#models-panel-installed")).toContainText(/Local Registry|No models registered/);

  await page.getByRole("tab", { name: "Running" }).click();
  await expect(page.locator("#models-panel-running")).toBeVisible();
  await expect(page.locator("#models-panel-running")).toContainText("Infrastructure");

  await page.getByRole("tab", { name: "Settings" }).click();
  await expect(page.locator("#models-panel-settings")).toContainText("Testing Mode");
  const testingModeButton = page.locator("#models-panel-settings").getByRole("button", { name: "Enable", exact: true });
  if (await testingModeButton.count()) {
    await testingModeButton.click();
  }

  await page.locator("[data-testid='nav-chat']").click();
  await expect(page.locator("#chatView")).toBeVisible();
  await page.locator("[data-testid='chat-model-chip']").click();
  await expect(page.locator("[data-testid='command-menu']")).toBeVisible();
  await expect(page.locator("[data-testid='command-menu']")).toContainText("Model");
  await page.locator("[data-testid='command-item']").filter({ hasText: "Testing Mode" }).click();
  await expect(page.locator("[data-testid='command-menu']")).toBeHidden();
  await expect(page.locator("[data-testid='chat-model-chip']")).toContainText("Testing Mode");
  await page.locator("#objective").fill("Testing the Rasputin UI harness.");
  await page.locator("#sendBtn").click();

  await expect(page.locator(".thread-list")).toContainText("Testing the Rasputin UI harness.");
  await expect(page.locator(".thread-list")).toContainText("done", { timeout: 45000 });

  await page.locator("[data-testid='runtime-details-toggle'] summary").first().click();
  await page.locator("[data-testid='activity-task-details']").first().click();
  await expect(page.locator("[data-testid='task-details-drawer']")).toBeVisible();
  await expect(page.locator("[data-testid='task-details-drawer']")).toContainText("Testing the Rasputin UI harness.");
  await expect(page.locator("[data-testid='task-details-overview']")).toBeVisible();
  const overviewTab = page.getByRole("tab", { name: "Overview" });
  await overviewTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Changes" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("[data-testid='task-details-changes']")).toBeVisible();
  await expect(page.locator("[data-testid='task-changes']")).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Terminal" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("[data-testid='task-details-terminal']")).toBeVisible();
  await expect(page.locator("[data-testid='task-details-terminal']")).toContainText("No shell or test-command output");
  await page.keyboard.press("Home");
  await expect(overviewTab).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "What Rasputin Saw" }).click();
  await expect(page.locator("[data-testid='task-context-budget']")).toBeVisible();
  await expect(page.locator("[data-testid='task-context-budget']")).toContainText("Context Budget");
  await page.getByRole("tab", { name: "Logs" }).click();
  await expect(page.locator("[data-testid='task-details-logs']")).toBeVisible();
  await page.getByRole("tab", { name: "Outputs" }).click();
  await expect(page.locator("[data-testid='task-details-outputs']")).toBeVisible();
  await page.getByRole("tab", { name: "Tools" }).click();
  await expect(page.locator("[data-testid='task-details-tools']")).toBeVisible();
  await expect(page.locator("[data-testid='task-details-tools']")).toContainText("No tool calls were recorded");
  await page.locator("[data-testid='task-details-close']").click();
  await expect(page.locator("[data-testid='task-details-drawer']")).toBeHidden();
});

test("workspace validation commands persist through the operator UI", async ({ page, request }) => {
  await page.goto("/");
  await waitForAppReady(page);
  await openShellView(page, "nav-workspaces");

  await expect(page.locator("[data-testid='workspace-command-settings']")).toBeVisible();
  await page.locator("[data-testid='workspace-test-command']").fill("pytest -q");
  await page.locator("[data-testid='workspace-build-command']").fill("npm run build");
  await page.locator("[data-testid='workspace-lint-command']").fill("npm run lint");
  await page.locator("[data-testid='workspace-save-commands']").click();
  await expect(
    page.locator("[data-testid='workspace-command-settings']").getByRole("status"),
  ).toContainText("Validation commands saved.", { timeout: 30000 });

  const workspaceResponse = await request.get("/api/workspace");
  const workspacePayload = await workspaceResponse.json();
  expect(workspacePayload.ok).toBe(true);
  const activeWorkspace = workspacePayload.data.workspaces.find(
    (workspace) => workspace.id === workspacePayload.data.activeId,
  );
  expect(activeWorkspace.commands).toEqual({
    test: "pytest -q",
    build: "npm run build",
    lint: "npm run lint",
  });
});

test("sidebar collapse persists and themes switch", async ({ page }) => {
  test.setTimeout(120000);
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
  await page.locator("[data-testid='settings-general']").click();
  const themeSelect = page.locator("#settingsShell select").first();
  await themeSelect.selectOption("rasputin-dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "rasputin-dark");
  await themeSelect.selectOption("bootswatch-slate");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "bootswatch-slate");
  await themeSelect.selectOption("contrast");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "contrast");
  await page.reload();
  await waitForAppReady(page);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "contrast");
  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-general']").click();
  await page.locator("#settingsShell select").first().selectOption("rasputin-light");
});

test("direct hash routes override saved active view preferences", async ({ page, request }) => {
  await request.post("/api/preferences", {
    data: {
      activeView: "settings",
      activeSettingsSection: "admin",
    },
  });

  await page.goto("/#models");
  await waitForAppReady(page);
  await expect(page.locator("#modelsView")).toBeVisible();
  await expect(page.locator("#settingsShell")).not.toBeVisible();

  await page.goto("/#settings/security");
  await waitForAppReady(page);
  await expect(page.locator("#settingsShell")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Security Center" })).toBeVisible();

  await page.goto("/#home");
  await waitForAppReady(page);
  await expect(page.locator("#homeView")).toBeVisible();
});

test("key settings destinations are reachable", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("#workspacesView")).toBeVisible();
  await expect(page.locator("[data-testid='workspace-runtime-mode']")).toBeVisible();
  await expect(page.locator("#workspacesView")).toContainText("Approved Folders");
  await expect(page.locator("#workspacesView")).toContainText("Knowledge Operations");
  await expect(page.locator("[data-testid='workspace-command-settings']")).toBeVisible();

  await page.locator("[data-testid='nav-settings']").click();
  await expect(page.locator("#settingsShell")).toBeVisible();
  for (const section of ["general", "models", "security", "integrations", "diagnostics", "about"]) {
    const button = page.locator(`[data-testid='settings-${section}']`);
    await expect(button).toBeVisible();
    await button.click();
    await expect(button).toHaveAttribute("aria-current", "page");
  }

  await page.locator("[data-testid='nav-assistant']").click();
  await expect(page.locator("#assistantView")).toBeVisible();
  await expect(page.locator("[data-testid='assistant-capability-contracts']")).toBeVisible();

  await page.locator("[data-testid='nav-activity']").click();
  await expect(page.locator("#activityView")).toBeVisible();
});

test("MCP capability contract stays fail-closed in the assistant UI", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-assistant']").click();
  await expect(page.locator("[data-testid='assistant-capability-contracts']")).toBeVisible();
  const mcp = page.locator("[data-testid='assistant-mcp-contract']");
  await expect(mcp).toBeVisible();
  await expect(mcp).toContainText("Fail-closed discovery");
  await expect(mcp).toContainText("Callable tools:");
  await expect(mcp).toContainText("Blocked by policy:");
});

test("activity hub groups runtime pages", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-activity']").click();
  await expect(page.locator("#activityView")).toBeVisible();
  await expect(page.locator("#activityView")).toContainText("Activity Center");
  for (const tab of ["Queue", "All Runs", "Active", "Completed", "Failed", "Scheduled"]) {
    await expect(page.getByRole("button", { name: tab, exact: true })).toBeVisible();
  }
  await page.getByRole("button", { name: "Queue", exact: true }).click();
  await expect(page.locator("#activityView")).toContainText("Persistent task queue");
  await page.getByRole("button", { name: "System Events", exact: true }).click();
  await expect(page.locator("#activityView")).toContainText("System Health Panel");
  await page.getByRole("button", { name: "Audit Log", exact: true }).click();
  await expect(page.locator("#activityView")).toContainText("Action Registry & Audit Log");
});

test("archive and trials views support first workflow", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await openShellView(page, "nav-archive");
  const archiveView = page.locator("#archiveView");
  await expect(archiveView).toBeVisible();
  await expect(archiveView).toContainText("Artifact Workspace");
  await expect(archiveView).toContainText("Task-linked by design");
  for (const filter of ["All artifacts", "Markdown", "Data & JSON", "Text", "Pinned"]) {
    await expect(archiveView.getByRole("button", { name: filter, exact: true })).toBeVisible();
  }
  await expect(archiveView.getByRole("textbox", { name: "Search artifacts" })).toBeVisible();
  await archiveView.getByRole("button", { name: "Refresh artifacts" }).click();

  await openShellView(page, "nav-trials");
  const trialsView = page.locator("#trialsView");
  await expect(trialsView).toBeVisible();
  await expect(trialsView).toContainText("Trials Lab");
  for (const tab of ["Experiments", "Coding Trial", "Benchmarks", "Prompt Lab", "Comparisons", "Datasets", "Reports"]) {
    await expect(trialsView.getByRole("button", { name: tab, exact: true })).toBeVisible();
  }
  await trialsView.getByRole("button", { name: "New Experiment", exact: true }).click();
  await expect(trialsView).toContainText("Create Experiment");
  await expect(trialsView.locator("input[name='name']")).toBeVisible();
  await expect(trialsView.locator("textarea[name='prompt']")).toBeVisible();
});

test("workspaces adapt to split-screen width", async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 760 });
  await page.goto("/");
  await waitForAppReady(page);
  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("#workspacesView")).toBeVisible();
  await expect(page.locator("[data-testid='workspace-runtime-mode']")).toBeVisible();

  const metrics = await page.locator("#workspacesView .w2-main-grid").evaluate((layout) => {
    const columns = Array.from(layout.children).map((node) => {
      const rect = node.getBoundingClientRect();
      return { width: Math.round(rect.width), height: Math.round(rect.height) };
    });
    return {
      overflowX: layout.scrollWidth - layout.clientWidth,
      columns,
    };
  });

  expect(metrics.columns.length).toBeGreaterThanOrEqual(2);
  expect(metrics.columns.every((column) => column.width > 0 && column.height > 0)).toBe(true);
  expect(metrics.overflowX).toBeLessThanOrEqual(2);
  await assertNoShellOverflow(page, "workspace split-screen");
});

test("primary views stay responsive across desktop split tablet and mobile", async ({ page }) => {
  test.setTimeout(180000);
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
    ["warsat", "nav-warsat", "#warsatView"],
    ["archive", "nav-archive", "#archiveView"],
    ["trials", "nav-trials", "#trialsView"],
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
      await assertVisibleButtonsAreNamed(page, `${viewportName}:${viewName}`);
    }

    await openShellView(page, "nav-settings");
    await page.locator("[data-testid='settings-security']").click();
    await expect(page.locator("#settingsShell")).toContainText("Security");
    await expect.poll(async () => page.locator("#settingsShell").evaluate((node) => node.scrollWidth - node.clientWidth), { timeout: 5000 }).toBeLessThanOrEqual(2);
    await assertNoShellOverflow(page, `${viewportName}:settings-security`);
    await assertVisibleButtonsAreNamed(page, `${viewportName}:settings-security`);
  }
});

test("chat sessions can be categorized into folders", async ({ page, request }) => {
  test.setTimeout(120000);
  const base = `Folder smoke chat ${Date.now()}`;
  const titles = Array.from({ length: 18 }, (_, index) => `${base} ${index + 1}`);
  const folderName = `UI Folder Smoke ${Date.now()}`;
  const folderResponse = await request.post("/api/chat-folders", { data: { name: folderName } });
  expect((await folderResponse.json()).ok).toBe(true);
  const createdTasks = [];
  for (const title of titles) {
    const response = await request.post("/api/tasks", {
      data: {
        objective: title,
        model: "dry-run",
        skill: "general",
        mode: "chat",
        workspacePath: ".",
      },
    });
    const body = await response.json();
    expect(body.ok).toBe(true);
    createdTasks.push(body.data);
  }

  await page.goto("/");
  await waitForAppReady(page);

  // The current shell keeps only a compact Recent Chats list in the rail;
  // the searchable, sortable library lives in the Sessions view.
  await page.locator("#rasputin-sidebar").getByRole("button", { name: "All", exact: true }).click();
  await expect(page.locator("#sessionsView")).toBeVisible();
  await page.locator("[data-testid='session-search']").fill(base);
  const smokeRows = page.locator("#sessionsView .session-list-item").filter({ hasText: base });
  await expect.poll(async () => smokeRows.count(), { timeout: 30000 }).toBe(18);
  await expect(smokeRows.first()).toContainText(titles[0]);
  await expect.poll(async () => {
    return page.locator("#sessionsView .session-scroll-list").evaluate((node) => node.scrollHeight > node.clientHeight);
  }).toBe(true);

  await expect.poll(async () => {
    return page.locator("[data-testid='chat-folder-list'] button").evaluateAll((buttons, name) => {
      return buttons.some((button) => button.textContent.includes(name));
    }, folderName);
  }, { timeout: 15000 }).toBe(true);

  const targetRow = page.locator("#sessionsView .session-list-item").filter({ hasText: titles[17] });
  await targetRow.getByRole("combobox", { name: `Move ${titles[17]} to folder` }).selectOption(folderName);
  const targetSessionId = createdTasks[17].sessionId;
  await expect.poll(async () => {
    const response = await request.get(`/api/sessions/${targetSessionId}`);
    const payload = await response.json();
    return payload?.data?.session?.folder || "";
  }, { timeout: 30000 }).toBe(folderName);
  await page.locator("[data-testid='chat-folder-list'] button").filter({ hasText: folderName }).click();
  await expect(page.locator("#sessionsView .session-scroll-list")).toContainText(titles[17], { timeout: 30000 });
});

test("warsat protocols produce dry-run launch plans", async ({ page }) => {
  const planRequests = [];
  await page.route("**/api/warsat/plan", async (route) => {
    const body = route.request().postDataJSON();
    planRequests.push(body);
    const isLlama = body.protocolId === "llamaCppGgufServer";
    const port = Number(body.hostPort) || (isLlama ? 8091 : 8020);
    const model = body.modelRef || body.modelPath || "test-model";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          planId: `ui-${isLlama ? "llama" : "vllm"}`,
          protocolId: body.protocolId,
          protocolName: isLlama ? "llama.cpp GGUF Server" : "vLLM CUDA OpenAI Server",
          runtime: isLlama ? "llama.cpp" : "vllm",
          modelRef: isLlama ? undefined : model,
          modelPath: isLlama ? body.modelPath || model : undefined,
          containerName: `rasputin-ui-${isLlama ? "llama" : "vllm"}`,
          endpoint: `http://127.0.0.1:${port}/v1`,
          expectedModelRegistryEntry: { baseUrl: `http://127.0.0.1:${port}/v1` },
          hostPort: port,
          strengthProfile: body.strengthProfile || "balanced",
          executionEnabled: false,
          dockerControlEnabled: false,
          dockerCliAvailable: true,
          approvalGranted: false,
          securityChecks: { localhostOnly: true },
          lifecycle: [
            { id: "planned", label: "Plan", status: "active" },
            { id: "probe", label: "Probe health", status: "pending" },
          ],
          dockerRun: `docker run --rm -p ${port}:8000 --max-model-len 8192 ${model}`,
          resourceAdmission: {
            status: "ready",
            placements: [{ deviceId: "gpu0", vramMb: 12000 }],
          },
          warnings: [],
        },
        error: null,
      }),
    });
  });

  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-warsat']").click();
  await expect(page.locator("[data-testid='warsat-view']")).toBeVisible();
  await page.getByRole("button", { name: "Deploy", exact: true }).click();
  const recipe = page.locator(".ws-mission-recipe").filter({ hasText: "Launch Recipe" });
  await expect(recipe).toBeVisible();
  await recipe.locator("select[name='protocolId']").selectOption("vllmCudaOpenai");
  await recipe.locator("input[name='modelRef']").fill("Qwen/Qwen2.5-Coder-7B-Instruct");
  await recipe.locator("input[name='hostPort']").fill("8020");
  await recipe.locator("select[name='role']").selectOption("coder");
  await recipe.locator("input[name='toolCallParser']").fill("hermes");
  await recipe.getByRole("button", { name: "Generate Plan" }).click();
  await expect.poll(() => planRequests.length).toBe(1);
  expect(planRequests[0]).toMatchObject({ protocolId: "vllmCudaOpenai", modelRef: "Qwen/Qwen2.5-Coder-7B-Instruct", hostPort: 8020, toolCallParser: "hermes" });
  const brief = page.locator(".ws-mission-brief");
  await expect(brief).toBeVisible();
  await expect(brief).toContainText("vLLM CUDA OpenAI Server");
  await expect(brief).toContainText("Plan only");
  await expect(brief).toContainText("localhost only");
  await expect(brief).toContainText("http://127.0.0.1:8020/v1");
  await expect(brief).toContainText("Probe health");
  await expect(brief).toContainText("docker run");
  await expect(page.locator("[data-testid='warsat-resource-admission']")).toContainText("Resource admission: Ready");

  await recipe.getByRole("button", { name: "Clear" }).click();
  await recipe.locator("select[name='protocolId']").selectOption("llamaCppGgufServer");
  await recipe.locator("input[name='modelPath']").fill("models/tiny-helper.gguf");
  await recipe.locator("input[name='hostPort']").fill("8091");
  await recipe.locator("select[name='strengthProfile']").selectOption("small");
  await recipe.getByRole("button", { name: "Generate Plan" }).click();
  await expect.poll(() => planRequests.length).toBe(2);
  await expect(page.locator(".ws-mission-brief")).toContainText("llama.cpp GGUF Server");
  await expect(page.locator(".ws-mission-brief")).toContainText("models/tiny-helper.gguf");
});

test("models catalog can prepare approve and complete a safe Warsat deployment QA flow", async ({ page }) => {
  test.setTimeout(120000);
  let approvalStatus = "pending";
  let deploymentDone = false;
  let deployCalls = 0;
  const approval = {
    id: "approval-ui-warsat",
    code: "WS-UI-42",
    status: "pending",
    action_type: "warsat_deploy",
    summary: "Deploy Qwen Coder through WarSat",
  };

  await page.route("**/api/model-catalog?fit=true", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          items: [{
            id: "Qwen/Qwen2.5-Coder-7B-Instruct",
            modelId: "Qwen/Qwen2.5-Coder-7B-Instruct",
            name: "Qwen2.5 Coder",
            purpose: "coding",
            capabilities: ["coding", "tools"],
            deployable: true,
            recommendedProtocol: "vllmCudaOpenai",
            toolCallParserHint: "hermes",
            contextWindow: 16384,
            vramEstimateGb: 12,
            fitLabel: "Strong fit",
            runtimeOptions: [{ protocolId: "vllmCudaOpenai" }],
          }],
          categories: [{ id: "coding", label: "Coding" }],
          runtimes: [{ id: "vllmCudaOpenai", label: "vLLM" }],
        },
        error: null,
      }),
    });
  });
  await page.route("**/api/model-registry", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          models: deploymentDone ? [{
            key: "qwen-ui-warsat",
            name: "Qwen2.5 Coder",
            model: "Qwen/Qwen2.5-Coder-7B-Instruct",
            provider: "vllm",
            runtime: "vllm",
            role: "coder",
            status: "reachable",
            managed: true,
          }] : [],
        },
      }),
    });
  });
  await page.route("**/api/warsat/protocols", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: {
        protocols: [{ id: "vllmCudaOpenai", name: "vLLM CUDA OpenAI Server", runtime: "vllm", modelFormat: "huggingface", defaultRole: "coder" }],
        strengthProfiles: { balanced: { label: "Balanced" } },
        dockerControlEnabled: true,
        executionEnabled: true,
      } }),
    });
  });
  await page.route("**/api/warsat/runtimes", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, data: { containers: [], count: 0 } }) });
  });
  await page.route("**/api/warsat/hardware", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, data: {
      status: "ready",
      checks: [],
      detectedHardware: { gpus: [{ index: 0, name: "QA GPU", memoryTotalMb: 16384 }] },
      capabilityProfile: { source: "ui-test" },
    } }) });
  });
  await page.route("**/api/warsat/plan", async (route) => {
    const body = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          planId: "plan-ui-warsat",
          protocolId: body.protocolId,
          protocolName: "vLLM CUDA OpenAI Server",
          runtime: "vllm",
          modelRef: body.modelRef,
          containerName: "rasputin-ui-warsat",
          hostPort: 8021,
          endpoint: "http://127.0.0.1:8021/v1",
          expectedModelRegistryEntry: { baseUrl: "http://127.0.0.1:8021/v1" },
          strengthProfile: "balanced",
          executionEnabled: true,
          dockerControlEnabled: true,
          dockerCliAvailable: true,
          approvalGranted: false,
          securityChecks: { localhostOnly: true },
          resourceAdmission: { status: "ready", placements: [{ deviceId: "gpu0", vramMb: 12000 }] },
          lifecycle: [
            { id: "planned", label: "Plan", status: "active" },
            { id: "approvalPending", label: "Approve", status: "pending" },
          ],
          dockerRun: "docker run --rm -p 8021:8000 qwen-coder",
          warnings: [],
        },
      }),
    });
  });
  await page.route("**/api/approvals*", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, data: {
      approvals: [{ ...approval, status: approvalStatus }],
    } }) });
  });
  await page.route("**/api/approvals/approval-ui-warsat/approve", async (route) => {
    approvalStatus = "approved";
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, data: { ...approval, status: approvalStatus } }) });
  });
  await page.route("**/api/warsat/deploy", async (route) => {
    deployCalls += 1;
    if (deployCalls === 1) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, data: {
        status: "pending",
        phase: "approvalPending",
        approvalRequired: true,
        approval,
        lifecycle: [
          { id: "planned", label: "Plan", status: "done" },
          { id: "approvalPending", label: "Approve", status: "active" },
        ],
      } }) });
      return;
    }
    deploymentDone = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          status: "registered",
          phase: "registered",
          endpoint: "http://127.0.0.1:8021/v1",
          modelKey: "qwen-ui-warsat",
          lifecycle: [
            { id: "planned", label: "Plan", status: "done" },
            { id: "approvalPending", label: "Approve", status: "done" },
            { id: "registered", label: "Register model", status: "done", message: "registered · reachable · test mode" },
          ],
        },
      }),
    });
  });

  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("#modelsView")).toBeVisible();
  await expect(page.locator("#models-tab-library")).toHaveAttribute("aria-selected", "true");
  const catalogCard = page.locator(".ras-list-item").filter({ hasText: "Qwen2.5 Coder" });
  await expect(catalogCard).toBeVisible();
  await catalogCard.getByRole("button", { name: "Deploy via Warsat" }).click();

  await expect(page.locator("[data-testid='warsat-view']")).toBeVisible();
  const missionBrief = page.locator(".ws-mission-brief");
  await expect(missionBrief).toBeVisible({ timeout: 30000 });
  await expect(missionBrief).toContainText("Qwen/Qwen2.5-Coder-7B-Instruct");
  await expect(missionBrief).toContainText("Execution enabled");
  await expect(missionBrief).toContainText("localhost only");
  const deployButton = missionBrief.getByRole("button", { name: "Request deploy approval", exact: true });
  await expect(deployButton).toBeEnabled();
  await assertNoShellOverflow(page, "warsat:prepared-deploy-flow");

  await deployButton.click();
  await expect(missionBrief.getByRole("button", { name: "Approve", exact: true })).toBeVisible();

  await missionBrief.getByRole("button", { name: "Approve", exact: true }).click();
  await expect.poll(() => deployCalls).toBe(2);
  await expect(missionBrief).toContainText("Model registered", { timeout: 30000 });
  await expect(missionBrief).toContainText("registered · reachable · test mode");
  await expect(missionBrief).toContainText("http://127.0.0.1:8021/v1");
  await assertNoShellOverflow(page, "warsat:registered-deploy-flow");

  await page.locator("[data-testid='nav-models']").click();
  await page.locator("#models-tab-installed").click();
  await expect(page.locator("#models-panel-installed")).toContainText("Qwen2.5 Coder");
});

test("visual review screenshots", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);
  await page.locator("[data-testid='nav-home']").click();
  await page.locator("[data-testid='nav-chat']").click();
  await expect(page.locator("#chatView")).toBeVisible();

  await page.locator("[data-testid='chat-mode-chip']").click();
  await expect(page.locator("[data-testid='command-menu']")).toBeVisible();
  await expect(page.locator("[data-testid='command-menu']")).toContainText("Mode");
  await page.screenshot({ path: `${screenshotDir}/mode-menu.png`, fullPage: true });
  await page.keyboard.press("Escape");

  await page.screenshot({ path: `${screenshotDir}/home-desktop.png`, fullPage: true });

  await page.locator("[data-testid='sidebar-toggle']").click();
  await page.screenshot({ path: `${screenshotDir}/sidebar-collapsed.png`, fullPage: true });
  await page.locator("[data-testid='sidebar-toggle']").click();

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("#modelsView")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/models.png`, fullPage: true });

  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("#workspacesView")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/workspaces.png`, fullPage: true });

  await page.locator("[data-testid='nav-activity']").click();
  await expect(page.locator("#activityView")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/activity.png`, fullPage: true });

  await page.locator("[data-testid='nav-warsat']").click();
  await expect(page.locator("[data-testid='warsat-view']")).toBeVisible();
  await page.screenshot({ path: `${screenshotDir}/warsat.png`, fullPage: true });

  await page.locator("[data-testid='nav-settings']").click();
  await expect(page.locator("#settingsShell")).toBeVisible();
  await page.locator("[data-testid='settings-general']").click();
  await page.locator("#settingsShell").getByRole("combobox").first().selectOption("rasputin-dark");
  await page.screenshot({ path: `${screenshotDir}/dark-theme.png`, fullPage: true });

  await page.locator("#settingsShell").getByRole("combobox").first().selectOption("rasputin-light");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("[data-testid='mobile-sidebar-toggle']").click();
  await page.locator("[data-testid='nav-home']").click();
  await page.screenshot({ path: `${screenshotDir}/home-mobile.png`, fullPage: true });
});
