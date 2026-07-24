import { expect, test } from "@playwright/test";

test("Trials exposes the repeatable blind comparison contract", async ({ page, request }) => {
  if (process.env.RASPUTIN_TEST_PASSWORD) {
    const login = await request.post("/api/auth/login", {
      data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
    });
    expect((await login.json()).ok).toBe(true);
    const state = await request.storageState();
    await page.context().addCookies(state.cookies);
  }

  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  await page.locator("[data-testid='nav-trials']").click();
  await page.getByRole("button", { name: "New Blind Compare" }).click();

  const form = page.locator("[data-testid='blind-compare-form']");
  await expect(form).toContainText("Model identities stay hidden until reveal");
  await expect(form.getByLabel("Repetitions")).toHaveValue("3");
  await expect(form.getByLabel("Saved seed")).toHaveValue("rasputin");
  await expect(form.getByRole("button", { name: "Run blind comparison" })).toBeVisible();
});
