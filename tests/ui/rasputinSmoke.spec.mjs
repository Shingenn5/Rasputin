import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const screenshotDir = "test-results/rasputin-screenshots";
const workspaceHostRoot = (process.env.RASPUTIN_TEST_WORKSPACE_DIR || "./testdata/workspace").replaceAll("\\", "/");

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

test("home shell settings and dry-run task work", async ({ page, request }) => {
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
  await expect(page.locator("[data-testid='agent-lanes']")).toBeVisible();
  await expect(page.locator("[data-testid='agent-lane']")).toHaveCount(7);
  await expect(page.locator("[data-testid='agent-lane']").filter({ hasText: "Chat" })).toHaveAttribute("aria-selected", "true");
  await page.locator("[data-testid='agent-lane']").filter({ hasText: "Research" }).click();
  await expect(page.locator("[data-testid='chat-mode-chip']")).toContainText("Research");
  await expect(page.locator("[data-testid='active-agent-lane']")).toContainText("Research");
  await page.locator("[data-testid='agent-lane']").filter({ hasText: "Chat" }).click();
  await expect(page.locator("[data-testid='chat-mode-chip']")).toContainText("Chat");
  await page.locator("[data-testid='chat-mode-chip']").click();
  await expect(page.locator("[data-testid='mode-side-panel']")).toBeVisible();
  await expect(page.locator("[data-testid='mode-option']")).toHaveCount(7);
  await page.locator("[data-testid='mode-option']").filter({ hasText: "Code" }).getByRole("button", { name: /Code/ }).click();
  await expect(page.locator("[data-testid='chat-mode-chip']")).toContainText("Code");
  await expect(page.locator("#objective")).toBeVisible();
  await expect(page.locator("#selectedModelHealth")).toBeVisible();
  await expect(page.locator("#welcomePanel")).toBeAttached();
  await expect(page.locator("#welcomePanel")).toBeVisible();
  await expect(page.locator("#tasks")).not.toContainText("Testing the Rasputin live smoke harness.");
  const sessionsBefore = await request.get("/api/sessions");
  const sessionsBeforeBody = await sessionsBefore.json();
  const sessionIdsBefore = new Set((sessionsBeforeBody.data?.sessions || []).map((session) => session.id));
  await page.locator("[data-testid='new-task']").click();
  await expect(page.locator("#globalStatus")).toContainText("New chat created");
  const sessionsResponse = await request.get("/api/sessions");
  const sessionsBody = await sessionsResponse.json();
  expect(sessionsBody.ok).toBe(true);
  expect(sessionsBody.data.sessions.some((session) => !sessionIdsBefore.has(session.id))).toBe(true);

  await page.locator("[data-testid='nav-models']").click();
  await expect(page.locator("#modelsView")).toBeVisible();
  await expect(page.locator("[data-testid='model-readiness-panel']")).toBeVisible();
  await expect(page.locator("[data-testid='model-readiness-panel']")).toContainText("Runtime Readiness");
  await expect(page.locator("[data-testid='model-readiness-panel']")).toContainText("Active chat model");
  await expect(page.locator("[data-testid='model-readiness-panel']")).toContainText("Context window");
  await expect(page.locator("[data-testid='model-readiness-panel']")).toContainText("Warsat hardware");
  await expect(page.locator("[data-testid='active-model-card']")).not.toContainText("Main Local Model");
  await page.locator("[data-testid='models-dev-catalog']").scrollIntoViewIfNeeded();
  await expect(page.locator("[data-testid='models-dev-catalog']")).toBeVisible();
  await expect(page.locator("[data-testid='catalog-model-card']").first()).toBeVisible();
  await expect(page.locator("[data-testid='catalog-send-to-warsat']")).toBeVisible();
  await expect(page.locator("#modelsView")).toContainText("Warsat Deployment Plan");
  await expect(page.locator("[data-testid='advanced-model-registry']")).toBeVisible();
  await expect(page.locator("[data-testid='gguf-scan']")).toBeVisible();
  await page.locator("[data-testid='advanced-model-registry'] summary").click();
  await expect(page.locator("#modelRegistry")).toContainText("Testing Mode");
  await page.locator("[data-testid='testing-mode-action']").scrollIntoViewIfNeeded();
  await page.locator("[data-testid='testing-mode-action']").click();

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
  await expect(page.locator("#tasks")).toContainText("done", { timeout: 45000 });

  await page.locator("[data-testid='runtime-details-toggle'] summary").first().click();
  await page.locator("[data-testid='activity-task-details']").first().click();
  await expect(page.locator("[data-testid='task-details-drawer']")).toBeVisible();
  await expect(page.locator("[data-testid='task-details-drawer']")).toContainText("Testing the Rasputin UI harness.");
  await expect(page.locator("[data-testid='task-details-overview']")).toBeVisible();
  await page.getByRole("tab", { name: "What Rasputin Saw" }).click();
  await expect(page.locator("[data-testid='task-context-budget']")).toBeVisible();
  await expect(page.locator("[data-testid='task-context-budget']")).toContainText("Context Budget");
  await page.getByRole("tab", { name: "Logs" }).click();
  await expect(page.locator("[data-testid='task-details-logs']")).toBeVisible();
  await page.getByRole("tab", { name: "Outputs" }).click();
  await expect(page.locator("[data-testid='task-details-outputs']")).toBeVisible();
  await page.getByRole("tab", { name: "Tools" }).click();
  await expect(page.locator("[data-testid='task-details-tools']")).toBeVisible();
  await expect(page.locator("[data-testid='task-details-tools']")).toContainText(/Rag Search|Graph Search|File Tree/);
  await page.locator("[data-testid='task-details-close']").click();
  await expect(page.locator("[data-testid='task-details-drawer']")).toBeHidden();
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

test("key settings destinations are reachable", async ({ page, request }) => {
  test.setTimeout(150000);
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("#workspacesView")).toBeVisible();
  await expect(page.locator("[data-testid='workspace-browser']")).toBeVisible();
  await expect(page.locator("[data-testid='workspace-knowledge-flow']")).toBeVisible();
  await expect(page.locator("[data-testid='workspace-knowledge-flow']")).toContainText("Local File Test Flow");
  await expect(page.locator("[data-testid='workspace-knowledge-panel']")).toBeVisible();
  await expect(page.locator("#workspaceRootList")).not.toBeEmpty();
  await expect(page.locator("#workspaceEntries")).toBeVisible();
  await expect(page.locator("[data-testid='workspace-root-card']:visible").first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator("[data-testid='workspace-file-row']:visible").first()).toBeVisible({ timeout: 30000 });
  const previewRow = page.locator("[data-testid='workspace-file-row']").filter({ hasText: "requirements.txt" }).first();
  await expect(previewRow).toBeVisible();
  await previewRow.getByRole("button", { name: /requirements\.txt/ }).click();
  await expect(page.locator("[data-testid='workspace-preview-panel']")).toContainText("requirements.txt");
  await expect(page.locator("[data-testid='workspace-preview-panel']")).toContainText("fastapi");
  await page.locator("[data-testid='workspace-knowledge-panel']").getByRole("button", { name: "Refresh stats" }).click();
  await expect(page.locator("[data-testid='workspace-knowledge-panel']")).toContainText("Docs");

  const graphRelativeDir = `ui-graph-smoke-${Date.now()}`;
  const graphDir = `workspace/${graphRelativeDir}`;
  const graphHostDir = `${workspaceHostRoot}/${graphRelativeDir}`;
  mkdirSync(graphHostDir, { recursive: true });
  writeFileSync(
    `${graphHostDir}/engine.py`,
    [
      "class WarmindNode:",
      "    def transmit_signal(self):",
      "        return parse_signal('warsat')",
      "def parse_signal(value):",
      "    return value",
    ].join("\n"),
  );
  writeFileSync(`${graphHostDir}/notes.md`, "WarmindNode evidence references engine.py and warsat signals.\n");
  await request.post("/api/workspace/approve", { data: { path: graphDir, name: "UI Graph Smoke", readOnly: true } });
  await request.post("/api/workspace/select", { data: { path: graphDir } });
  await request.post("/api/rag/ingest", { data: { path: graphDir, label: "UI Graph Smoke" } });
  await request.post("/api/graph/build", { data: { path: graphDir } });
  await page.reload();
  await waitForAppReady(page);
  await page.locator("[data-testid='nav-workspaces']").click();
  await page.locator("[data-testid='workspace-knowledge-panel'] input").fill("WarmindNode engine.py");
  await page.locator("[data-testid='workspace-knowledge-panel']").getByRole("button", { name: "Search" }).click();
  await expect(page.locator("[data-testid='workspace-knowledge-panel']")).toContainText("Docs");
  await expect(page.locator("[data-testid='workspace-rag-results']")).toContainText("RAG retrieval hits");
  await expect(page.locator("[data-testid='workspace-graph-results']")).toContainText("Graphify evidence");
  const graphSearch = await request.post("/api/graph/search", { data: { query: "WarmindNode engine.py", limit: 5 } });
  const graphPayload = await graphSearch.json();
  expect((graphPayload?.data?.nodes || []).length + (graphPayload?.data?.edges || []).length).toBeGreaterThan(0);
  await page.locator("[data-testid='workspace-load-analysis-prompt']").click();
  await expect(page.locator("#homeView")).toBeVisible();
  await expect(page.locator("#objective")).toHaveValue(/Analyze the approved workspace/);
  await page.locator("[data-testid='nav-workspaces']").click();
  await expect(page.locator("[data-testid='workspace-browser']")).toBeVisible();

  await page.locator(".workspace-mount-panel summary").click();
  await page.locator("#workspaceMountForm #mountHostPath").fill("C:\\Users\\example\\Documents");
  await page.locator("#workspaceMountForm").evaluate(form => form.requestSubmit());
  await expect(page.locator("[data-testid='workspace-mount-plan']")).toContainText("Read-only");

  await page.locator("[data-testid='nav-settings']").click();
  await expect(page.locator("[data-testid='setup-checklist']")).toBeVisible();
  await expect(page.locator("[data-testid='setup-step-admin']")).toContainText("Secure local admin login");
  await expect(page.locator("[data-testid='setup-step-model']")).toContainText("Connect a chat model");
  await page.locator("[data-testid='setup-step-model']").getByRole("button", { name: "Open Models" }).click();
  await expect(page.locator("#modelsView")).toBeVisible();
  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-safety']").click();
  await expect(page.locator("#securityForm")).toBeVisible();
  await expect(page.locator("[data-testid='save-safety']")).toBeDisabled();
  await page.getByLabel("Docker control").check();
  await expect(page.locator("#securityForm")).toContainText("Unsaved safety changes");
  await expect(page.locator("[data-testid='save-safety']")).toBeEnabled();
  await page.locator("#securityForm").getByRole("button", { name: "Reset" }).click();
  await expect(page.locator("[data-testid='save-safety']")).toBeDisabled();

  await page.locator("[data-testid='settings-tool-relays']").click();
  await expect(page.locator("#settings-tool-relays")).toBeVisible();
  await expect(page.locator("[data-testid='mcp-register-form']")).toBeVisible();
  await expect(page.locator("#settings-tool-relays")).toContainText("Compatibility");
  await expect(page.locator("#settings-tool-relays")).toContainText("Resources");
  await expect(page.locator("#settings-tool-relays")).toContainText("Prompts");
  await expect(page.locator("#settings-tool-relays")).toContainText("Read-Only MCP Capabilities");
  await expect(page.locator("[data-testid='mcp-capability-list']")).toBeVisible();

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

test("operator MCP fixture can be verified end to end", async ({ page }) => {
  test.setTimeout(180000);
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-tool-relays']").click();
  await expect(page.locator("#settings-tool-relays")).toBeVisible();
  await page.locator("[data-testid='mcp-register-fixture']").click();
  const fixtureServer = page.locator("[data-testid='mcp-server-card']").filter({ hasText: "Operator MCP Fixture" });
  await expect(fixtureServer).toBeVisible();
  await fixtureServer.getByRole("button", { name: /Approve \+ Start/ }).click();
  await expect(fixtureServer).toContainText(/running|Approved/i, { timeout: 15000 });
  await fixtureServer.getByRole("button", { name: "Test" }).click();
  await expect(page.locator("#settings-tool-relays")).toContainText("Test MCP server complete", { timeout: 15000 });
  await fixtureServer.getByRole("button", { name: "Discover Capabilities" }).click();
  await expect(page.locator("[data-testid='mcp-capability-list']")).toContainText("Operator fixture readme", { timeout: 15000 });
  const fixtureTool = page.locator(".tool-relay-card").filter({ hasText: "Fixture Status" });
  await expect(fixtureTool).toBeVisible();
  await fixtureTool.getByRole("button", { name: "Guarded Read" }).click();
  await expect(fixtureTool).toContainText("Available", { timeout: 15000 });
  await page.getByRole("button", { name: "Run safe MCP test call for Operator MCP Fixture: Fixture Status" }).click();
  await expect(page.locator("[data-testid='task-details-drawer']")).toBeVisible({ timeout: 15000 });
  await page.getByRole("tab", { name: "Tools" }).click();
  await expect(page.locator("[data-testid='task-details-tools']")).toContainText("Operator Mcp Fixture");
  await expect(page.locator("[data-testid='task-details-tools']")).toContainText("fixture-ok");
  await page.locator("[data-testid='task-details-close']").click();
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
  await page.getByRole("tab", { name: "Tools" }).scrollIntoViewIfNeeded();
  await page.getByRole("tab", { name: "Tools" }).click();
  await expect(page.locator("#activity-panel-tools")).toBeVisible();
  await expect(page.locator("[data-testid='tool-relay-panel']")).toBeVisible();
  await expect(page.locator("[data-testid='tool-relay-panel']")).toContainText("Tool Relay");
  await expect(page.locator("[data-testid='tool-relay-card']").first()).toBeVisible();
  await page.getByRole("tab", { name: "Audit" }).click();
  await expect(page.locator("#activityAuditLog")).toBeVisible();
});

test("archive and trials views support first workflow", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await openShellView(page, "nav-archive");
  await expect(page.locator("[data-testid='archive-view']")).toBeVisible();
  const archiveTitle = `UI Archive Smoke ${Date.now()}`;
  await page.getByRole("button", { name: "New draft" }).click();
  await page.locator("[data-testid='archive-editor'] input[name='title']").fill(archiveTitle);
  await page.locator("[data-testid='archive-editor'] textarea[name='content']").fill("# Local Draft\n\nThis stays in Rasputin.");
  await page.locator("[data-testid='archive-editor']").getByRole("button", { name: "Save Draft" }).click();
  await expect(page.locator("[data-testid='archive-editor']")).toContainText("Saved", { timeout: 60000 });
  await page.getByRole("tab", { name: "Preview" }).click();
  await expect(page.locator("[data-testid='archive-preview']")).toContainText("Local Draft");
  await page.getByRole("tab", { name: "Sources" }).click();
  await expect(page.locator("[data-testid='archive-citations']")).toBeVisible();
  await page.locator("[data-testid='archive-citations'] input").fill("server.py");
  await page.locator("[data-testid='archive-citations']").getByRole("button", { name: "Search" }).click();
  await expect(page.locator("[data-testid='archive-citations']")).toContainText(/local references|No local citations/i, { timeout: 30000 });
  await page.getByRole("tab", { name: "Export" }).click();
  await expect(page.locator("[data-testid='archive-export']")).toContainText("Export Markdown");
  await expect.poll(async () => {
    const response = await page.request.get("/api/archive/sessions");
    const payload = await response.json();
    return Boolean(payload?.data?.sessions?.some((session) => session.title === archiveTitle));
  }, { timeout: 60000 }).toBe(true);

  await openShellView(page, "nav-trials");
  await expect(page.locator("[data-testid='trials-view']")).toBeVisible();
  await page.locator("[data-testid='trials-compose'] textarea[name='prompt']").fill("Answer with one short sentence.");
  await page.locator("[data-testid='trials-compose']").getByRole("button", { name: "Run Blind Trial" }).click();
  await expect(page.locator("[data-testid='trials-view']")).toContainText("finished", { timeout: 30000 });
  await expect(page.locator("[data-testid='trial-run-card']").first()).toBeVisible();
  await expect(page.locator("[data-testid='trial-run-card']").first()).not.toContainText("dry-run");
  await page.locator("[data-testid='trial-run-card']").first().getByRole("button", { name: "Reveal Models" }).click();
  await expect(page.locator("[data-testid='trial-run-card']").first()).toContainText("dry-run");
  const routeForm = page.locator("[data-testid='trial-run-card']").first().locator(".trial-route-form").first();
  await expect(routeForm).toBeVisible();
  await routeForm.locator("select[name='mode']").selectOption("code");
  await routeForm.getByRole("button", { name: "Save Route" }).click();
  await expect(page.locator("[data-testid='trials-view']")).toContainText("Saved", { timeout: 30000 });
  await expect(page.locator("[data-testid='trial-run-card']").first()).toContainText("Code routes to");
  const prefsResponse = await page.request.get("/api/preferences");
  const prefsPayload = await prefsResponse.json();
  expect(prefsPayload.data.modeModelOverrides.code).toBe("dry-run");
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
    ["warsat", "nav-warsat", "[data-testid='warsat-view']"],
    ["archive", "nav-archive", "[data-testid='archive-view']"],
    ["trials", "nav-trials", "[data-testid='trials-view']"],
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

  await expect.poll(async () => {
    return await page.locator("[data-testid='sidebar-folder-filter'] option").evaluateAll((options, name) => {
      return options.some((option) => option.textContent === name);
    }, folderName);
  }, { timeout: 15000 }).toBe(true);

  const targetRow = page.locator("[data-testid='sidebar-session-row']").filter({ hasText: titles[17] });
  await targetRow.locator("[data-testid='sidebar-session-folder']").selectOption(folderName);
  const targetSessionId = createdTasks[17].sessionId;
  await expect.poll(async () => {
    const response = await request.get(`/api/sessions/${targetSessionId}`);
    const payload = await response.json();
    return payload?.data?.session?.folder || "";
  }, { timeout: 30000 }).toBe(folderName);
  await page.locator("[data-testid='sidebar-folder-filter']").selectOption(folderName);
  await expect(page.locator("[data-testid='sidebar-session-list']")).toContainText(titles[17], { timeout: 30000 });
});

test("warsat protocols produce dry-run launch plans", async ({ page }) => {
  await page.goto("/");
  await waitForAppReady(page);

  await page.locator("[data-testid='nav-warsat']").click();
  await expect(page.locator("[data-testid='warsat-view']")).toBeVisible();
  await expect(page.locator("[data-testid='warsat-hardware-panel']")).toBeVisible();
  await expect(page.locator("[data-testid='warsat-hardware-check']:visible").first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator("[data-testid='warsat-model-finder']")).toBeVisible();
  await page.locator("[data-testid='warsat-catalog-card']").filter({ hasText: "Qwen2.5 Coder" }).click();
  await page.locator("[data-testid='warsat-catalog-create-plan']").click();
  await expect(page.locator("[data-testid='warsat-launch-plan']")).toContainText("Qwen/Qwen2.5-Coder-7B-Instruct");
  await page.locator("[data-testid='warsat-view']").getByRole("button", { name: "Clear plan" }).click();

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
  await expect(page.locator("[data-testid='warsat-lifecycle']")).toBeVisible();
  await expect(page.locator("[data-testid='warsat-lifecycle']")).toContainText("Probe health");
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
