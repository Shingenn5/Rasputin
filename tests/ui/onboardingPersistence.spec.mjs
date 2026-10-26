import { expect, test } from "@playwright/test";

test("welcome dismissal survives a fresh browser with no local storage", async ({ browser, baseURL }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated server");
  async function openApp() {
    const context = await browser.newContext({ baseURL });
    const login = await context.request.post("/api/auth/login", {
      data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
    const page = await context.newPage();
    await page.route("**/api/ui/bootstrap", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.data.models = [];
      await route.fulfill({ response, json: body });
    });
    await page.goto("/#chat");
    await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
    return { page, context };
  }

  const first = await openApp();
  try {
    await expect(first.page.getByRole("dialog", { name: "Welcome to Rasputin" })).toBeVisible();
    const saved = first.page.waitForResponse((response) =>
      response.url().endsWith("/api/preferences") &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().onboarded === true && response.ok());
    await first.page.getByRole("button", { name: "Skip for now" }).click();
    await saved;
  } finally {
    await first.context.close();
  }

  const second = await openApp();
  try {
    expect(await second.page.evaluate(() => localStorage.getItem("rasputin-onboarded"))).toBeNull();
    await expect(second.page.getByRole("dialog", { name: "Welcome to Rasputin" })).toHaveCount(0);
    await expect(second.page.locator("#objective")).toBeVisible();
    const prefs = await second.context.request.get("/api/preferences");
    expect((await prefs.json()).data.onboarded).toBe(true);
  } finally {
    await second.context.close();
  }
});
