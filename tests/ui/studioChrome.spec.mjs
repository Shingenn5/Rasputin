import { expect, test } from "@playwright/test";

const models = [
  { key: "studio-a", model: "Studio Alpha", role: "main", provider: "openai-compatible", runtime: "external-local", runtimeStatus: "reachable", enabled: true, contextWindow: 32768 },
  { key: "studio-b", model: "Studio Beta", role: "coder", provider: "openai-compatible", runtime: "external-local", runtimeStatus: "reachable", enabled: true, contextWindow: 8192 },
];

test.beforeEach(async ({ page, context }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated server");
  const login = await context.request.post("/api/auth/login", { data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD } });
  expect(login.ok()).toBeTruthy();
  await page.addInitScript(() => {
    if (!localStorage.getItem("rasputin-theme")) localStorage.setItem("rasputin-theme", "rasputin-dark");
    localStorage.setItem("rasputin-theme-explicit", "1");
    localStorage.setItem("rasputin-sidebar-collapsed", "false");
    if (!localStorage.getItem("rasputin-sidebar-width")) localStorage.setItem("rasputin-sidebar-width", "280");
  });
  await page.route("**/api/ui/bootstrap", async route => {
    const response = await route.fetch();
    const json = await response.json();
    json.data.security = { ...json.data.security, native: true, desktopOnly: true };
    json.data.preferences = { ...json.data.preferences, onboarded: true, sidebarCollapsed: false, selectedModel: "studio-a" };
    json.data.models = models;
    json.data.sessions = { sessions: [
      { id: "studio-session-one", title: "Plan the release", model: "Studio Alpha" },
      { id: "studio-session-two", title: "Review the interface", model: "Studio Beta" },
    ] };
    await route.fulfill({ json });
  });
  await page.route("**/api/model-registry", route => route.fulfill({ json: { ok: true, data: { models } } }));
  await page.goto("/#chat");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.locator("#objective")).toBeVisible();
});

test("expanded sidebar exposes recent conversations and keeps settings below the workspace groups", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const recents = page.getByTestId("sidebar-recent-sessions");
  await expect(recents.getByRole("button", { name: "Plan the release" })).toBeVisible();
  await expect(recents.getByRole("button", { name: "Review the interface" })).toBeVisible();
  const recentBounds = await recents.boundingBox();
  const settingsBounds = await page.getByTestId("nav-settings").boundingBox();
  expect(settingsBounds.y).toBeGreaterThan(recentBounds.y + recentBounds.height);
  await page.getByTestId("history-drawer-trigger").click();
  await expect(page.getByTestId("history-drawer")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(recents.getByRole("button", { name: "Plan the release" })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("visible-sidebar-redesign.png") });
});

test("REA welcome keeps the header removed and options available at every screen size", async ({ page }) => {
  for (const [width, height] of [[1440, 1000], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width, height });
    const chat = page.locator("#chatView");
    await expect(chat).toHaveClass(/studio-home\b.*\bis-welcome/);
    await expect(chat.locator(".cc-header")).toHaveCount(0);
    await expect(chat.getByText("Good to see you", { exact: true })).toBeVisible();
    await expect(chat.locator(".composer-actions").getByTestId("chat-model-chip")).toBeVisible();
    const options = page.getByTestId("response-options-trigger");
    await options.click();
    await expect(page.getByTestId("task-memory-mode-selector")).toBeVisible();
    await expect(page.getByTestId("chat-reasoning-chip")).toBeVisible();
    await options.press("Escape");
    await expect(page.getByTestId("task-memory-mode-selector")).toBeHidden();
    await expect(options).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: test.info().outputPath(`rea-welcome-${width}.png`) });
  }
});

test("sidebar search supports keyboard navigation, focus trapping and restoration", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const search = page.getByTestId("sidebar-search");
  await search.click();
  const dialog = page.getByRole("dialog", { name: "Command palette" });
  const input = dialog.getByRole("combobox");
  await expect(input).toBeFocused();
  const first = await input.getAttribute("aria-activedescendant");
  await input.press("ArrowDown");
  await expect(input).not.toHaveAttribute("aria-activedescendant", first);
  await input.press("Shift+Tab");
  expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
  await page.screenshot({ path: test.info().outputPath("command-palette.png") });
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(search).toBeFocused();
  await page.keyboard.press("Control+k");
  await expect(input).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(search).toBeFocused();
});

test("search remains reachable in the collapsed rail and mobile drawer with the light palette", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => localStorage.setItem("rasputin-theme", "rasputin-light"));
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "rasputin-light");
  await page.getByTestId("sidebar-toggle").click();
  await expect(page.getByTestId("sidebar-toggle")).toHaveAttribute("aria-label", "Expand sidebar");
  await page.getByTestId("sidebar-search").click();
  await expect(page.getByRole("dialog", { name: "Command palette" }).getByRole("combobox")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("sidebar-search")).toBeFocused();
  await page.getByTestId("sidebar-toggle").click();
  await expect.poll(async () => (await page.locator("#rasputin-sidebar").boundingBox()).width).toBe(280);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "rasputin-light");
  await page.screenshot({ path: test.info().outputPath("light-sidebar.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId("mobile-sidebar-toggle").click();
  await page.getByTestId("sidebar-search").click();
  await expect(page.getByRole("dialog", { name: "Command palette" }).getByRole("combobox")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("sidebar-search")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("mobile-sidebar-toggle")).toHaveAttribute("aria-expanded", "false");
});

test("recent chats traps focus and returns to its trigger", async ({ page }) => {
  const trigger = page.getByTestId("history-drawer-trigger");
  await trigger.click();
  const dialog = page.getByTestId("history-drawer");
  const input = page.getByTestId("history-search");
  await expect(input).toBeFocused();
  await input.press("Shift+Tab");
  await page.keyboard.press("Shift+Tab");
  expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("workstation sidebar resizes with mouse and keyboard, persists, and resets", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const separator = page.getByRole("separator", { name: "Resize sidebar" });
  await separator.focus();
  await page.keyboard.press("End");
  await expect(separator).toHaveAttribute("aria-valuenow", "400");
  await expect.poll(async () => (await page.locator("#rasputin-sidebar").boundingBox()).width).toBe(400);
  await page.keyboard.press("Home");
  await page.keyboard.press("Shift+ArrowRight");
  await expect(separator).toHaveAttribute("aria-valuenow", "260");
  const bounds = await separator.boundingBox();
  await page.mouse.move(bounds.x + bounds.width / 2, 320);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width / 2 + 60, 320);
  await page.mouse.up();
  await expect(separator).toHaveAttribute("aria-valuenow", "320");
  await page.reload();
  await expect(separator).toHaveAttribute("aria-valuenow", "320");
  await separator.dblclick();
  await expect(separator).toHaveAttribute("aria-valuenow", "280");
  await page.getByTestId("sidebar-toggle").click();
  await expect(separator).toHaveCount(0);
  await expect.poll(async () => (await page.locator("#rasputin-sidebar").boundingBox()).width).toBe(54);
  await page.getByTestId("sidebar-toggle").click();
  await expect(separator).toHaveAttribute("aria-valuenow", "280");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(separator).toBeHidden();
  await page.getByTestId("mobile-sidebar-toggle").click();
  await expect(page.getByTestId("nav-training")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
});

test("Library, Model Hub and retained tools have accessible navigation", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const library = page.getByTestId("nav-archive");
  const installed = page.getByTestId("nav-models");
  const hub = page.getByTestId("nav-discover");
  await library.click();
  await expect(library).toHaveAttribute("aria-current", "page");
  await expect(page.locator("#archiveView")).toBeVisible();
  await installed.click();
  await expect(page.locator("#modelsView h1")).toHaveText("Model Hub");
  await expect(page.locator("#models-tab-installed")).toHaveAttribute("aria-selected", "true");
  await page.locator(".studio-more-tools > summary").click();
  await hub.click();
  await expect(page).toHaveURL(/#discover$/);
  await expect(library).not.toHaveAttribute("aria-current", "page");
  await expect(page.locator("#modelsView h1")).toHaveText("Model Hub");
  await expect(page.locator("#models-tab-library")).toHaveAttribute("aria-selected", "true");
  await installed.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#models-tab-installed")).toHaveAttribute("aria-selected", "true");
  await page.getByTestId("nav-schedules").click();
  await expect(page.locator("#schedulesView")).toBeVisible();
  await expect(page.locator("#schedulesView button[type='submit']")).toBeEnabled();
});

test("model filter, selection and clear action work at desktop, tablet and phone widths", async ({ page }) => {
  for (const [width, height] of [[1440, 1000], [768, 1024], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await expect.poll(async () => (await page.locator("#mainContent").boundingBox()).width).toBe(width - (width >= 640 ? 280 : 0));
    const workspace = await page.locator("#mainContent").boundingBox();
    const composer = await page.locator("#objective").boundingBox();
    await page.getByTestId("chat-model-chip").click();
    const dialog = page.getByRole("dialog", { name: "Select a model to load" });
    const input = dialog.getByRole("searchbox", { name: "Filter available models" });
    await expect(input).toBeFocused();
    await input.fill("Beta");
    await expect(dialog.getByTestId("model-option")).toHaveCount(1);
    await dialog.getByRole("button", { name: "Clear model filter" }).click();
    await expect(input).toBeFocused();
    await expect(dialog.getByTestId("model-option")).toHaveCount(2);
    await input.fill("not-a-model");
    await expect(dialog.getByRole("status").filter({ hasText: "No available chat model" })).toBeVisible();
    await dialog.getByRole("button", { name: "Clear model filter" }).click();
    await dialog.getByTestId("model-option").filter({ hasText: "Studio Alpha" }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId("chat-selected-model-key")).toHaveAttribute("data-model-key", "studio-a");
    await page.getByTestId("chat-model-chip").click();
    await expect(dialog.getByTestId("model-option").filter({ hasText: "Studio Alpha" })).toHaveAttribute("aria-pressed", "true");
    await expect(dialog).toHaveCSS("opacity", "1");
    const bounds = await dialog.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
    expect(await dialog.evaluate(element => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: test.info().outputPath(`model-picker-${width}.png`) });
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId("chat-model-chip")).toBeFocused();
    expect(await page.locator("#mainContent").boundingBox()).toEqual(workspace);
    // Opening from the composer can scroll it into view on a phone.
    const restoredComposer = await page.locator("#objective").boundingBox();
    expect(restoredComposer.width).toBe(composer.width);
    expect(restoredComposer.height).toBe(composer.height);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  }
});
