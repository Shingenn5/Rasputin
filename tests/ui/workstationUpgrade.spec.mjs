import { expect, test } from "@playwright/test";

// Creating a key intentionally exposes its one-time secret in the form.
test.use({ trace: "off", screenshot: "off", video: "off" });

test.beforeEach(async ({ context, page }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated server");
  const login = await context.request.post("/api/auth/login", { data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD } });
  expect(login.ok()).toBeTruthy();
  await context.request.post("/api/preferences", { data: { onboarded: true } });
  await page.addInitScript(() => {
    localStorage.setItem("rasputin-sidebar-collapsed", "false");
    localStorage.setItem("rasputin-theme", "rasputin-dark");
    localStorage.setItem("rasputin-theme-explicit", "1");
  });
});

test("API creates a real key, hides it on navigation, and revokes access", async ({ page, context }) => {
  await page.goto("/#api");
  await expect(page.getByRole("heading", { name: "API", exact: true })).toBeVisible();
  await page.getByLabel("Key name", { exact: true }).fill("Browser verification");
  await page.getByRole("button", { name: "Create key", exact: true }).click();
  const secretInput = page.getByLabel("New API key", { exact: true });
  await expect(secretInput).toBeVisible();
  const secret = await secretInput.inputValue();
  expect(secret.startsWith("ras_sk_")).toBeTruthy();
  const headers = { Authorization: `Bearer ${secret}` };
  const accepted = await context.request.get("/v1/models", { headers });
  expect(accepted.status()).toBe(200);
  // Credentials are never included in screenshots, traces or assertion text.
  await page.getByRole("button", { name: "Hide key", exact: true }).click();
  await expect(secretInput).toHaveCount(0);
  await page.getByRole("button", { name: "Revoke Browser verification", exact: true }).click();
  await expect(page.getByRole("button", { name: "Revoke Browser verification", exact: true })).toHaveCount(0);
  const rejected = await context.request.get("/v1/models", { headers });
  expect(rejected.status()).toBe(401);
  await page.screenshot({ path: test.info().outputPath("api-keys-revoked.png") });
});

test("training blocks invalid datasets and reports runtime setup before starting", async ({ page }) => {
  await page.goto("/#training");
  await expect(page.getByRole("heading", { name: "Training", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start fine-tune", exact: true })).toBeDisabled();
  await page.getByLabel("Local base model directory", { exact: true }).fill("missing-model-directory");
  await page.getByLabel("Training examples", { exact: true }).fill("not json");
  await page.getByRole("button", { name: "Check readiness", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("not valid JSON");
  await expect(page.getByRole("button", { name: "Start fine-tune", exact: true })).toBeDisabled();
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByLabel("Training examples", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
    await page.screenshot({ path: test.info().outputPath(`training-${width}.png`) });
  }
});

test("API connection controls fit desktop tablet and phone", async ({ page }) => {
  await page.goto("/#api");
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByLabel("Base URL", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
    await page.getByLabel("Key name", { exact: true }).focus();
    await expect(page.getByLabel("Key name", { exact: true })).toBeFocused();
    await page.screenshot({ path: test.info().outputPath(`api-${width}.png`) });
  }
});
