import { expect, test } from "@playwright/test";

test.beforeEach(async ({ context, baseURL }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated Native Host");
  expect(new URL(baseURL).hostname).toBe("127.0.0.1");
  const login = await context.request.post("/api/auth/login", {
    data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  expect((await context.request.post("/api/preferences", { data: { onboarded: true } })).ok()).toBeTruthy();
});

test("Chat defers secondary chunks and preserves a Settings draft after navigation", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/#chat");
  await page.locator("body[data-ready='true']").waitFor();
  const resources = await page.evaluate(() => performance.getEntriesByType("resource").map(entry => entry.name));
  expect(resources.filter(url => /\/(DashboardView|ModelsView|SettingsView|WorkspacesView)-/.test(url))).toEqual([]);
  await page.getByTestId("nav-settings").click();
  const draft = page.getByPlaceholder("/var/rasputin/workspace", { exact: true });
  await draft.fill("C:/isolated-startup-draft");
  await page.getByTestId("nav-chat").focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#chat$/);
  await page.getByTestId("nav-settings").click();
  await expect(draft).toHaveValue("C:/isolated-startup-draft");
  expect(errors).toEqual([]);
});

test("all deferred pages load on their first explicit visit", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  for (const route of ["home", "models", "discover", "project", "settings/general"]) {
    await page.goto(`/#${route}`);
    await page.locator("body[data-ready='true']").waitFor();
    await expect(page.locator(".app-view.active").first()).toBeVisible();
    await expect(page.getByText("This page could not load.", { exact: true })).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});

test("a failed lazy chunk provides an accessible recovery action", async ({ page }) => {
  await page.route("**/SettingsView-*.js", route => route.abort());
  await page.goto("/#settings/general");
  await expect(page.getByRole("alert").filter({ hasText: "This page could not load" })).toBeVisible();
  const reload = page.getByRole("button", { name: "Reload application", exact: true });
  await reload.focus();
  await expect(reload).toBeFocused();
});
