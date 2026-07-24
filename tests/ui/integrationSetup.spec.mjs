import { expect, test } from "@playwright/test";

test("every Connector Center setup action opens a visible configuration dialog", async ({ page, request }) => {
  if (process.env.RASPUTIN_TEST_PASSWORD) {
    const login = await request.post("/api/auth/login", {
      data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
    });
    expect((await login.json()).ok).toBe(true);
    const state = await request.storageState();
    await page.context().addCookies(state.cookies);
  }

  const connectorResponse = await request.get("/api/connectors");
  const connectorPayload = await connectorResponse.json();
  expect(connectorPayload.ok).toBe(true);
  const providers = connectorPayload.data.providers;
  expect(providers.length).toBeGreaterThan(0);

  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  await page.locator("[data-testid='nav-settings']").click();
  await page.locator("[data-testid='settings-integrations']").click();

  for (const provider of providers) {
    const card = page.locator("article").filter({ hasText: provider.name });
    await card.getByRole("button", { name: /Set up|Configure/ }).click();
    const dialog = page.locator("[data-testid='connector-setup-dialog']");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(`Configure ${provider.name}`);
    await expect(dialog.getByLabel("Connection name")).toBeFocused();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
  }
});
