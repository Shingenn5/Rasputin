import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test("an unconfigured app acquires its verified runtime and runs an approved snapshot", async ({ page, context }) => {
  test.skip(!process.env.RASPUTIN_RUNTIME_WORKSPACE, "Requires the isolated native runtime setup harness");
  test.setTimeout(180000);
  const manifest = JSON.parse(readFileSync(new URL("../../runtime/execution/manifest.json", import.meta.url), "utf8"));
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  expect((await context.request.post("/api/auth/login", { data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD } })).ok()).toBeTruthy();
  await context.request.post("/api/preferences", { data: { onboarded: true } });
  await context.request.post("/api/security", { data: { offlineLock: true } });
  await page.goto("/#approvals");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
  const setup = page.getByTestId("sandbox-runtime-setup");
  await expect(setup.getByRole("button", { name: "Set up sandbox runtime", exact: true })).toBeDisabled();
  await expect(setup).toContainText("Offline mode blocks this download.");
  await context.request.post("/api/security", { data: { offlineLock: false } });
  await setup.getByRole("button", { name: "Refresh runtime", exact: true }).click();
  const install = setup.getByRole("button", { name: "Set up sandbox runtime", exact: true });
  await expect(install).toBeEnabled();
  await install.focus();
  await page.keyboard.press("Enter");
  await expect(setup).toContainText("Managed sandbox runtime ready.", { timeout: 120000 });
  const status = (await (await context.request.get("/api/execution/runtime")).json()).data;
  expect(status.installed).toBe(true);
  expect(status.version).toBe(manifest.version);
  expect(status.downloadedBytes).toBe(status.totalBytes);
  const capability = (await (await context.request.get("/api/execution")).json()).data;
  expect(capability.available).toBe(true);
  expect(capability.toolchain.managed).toBe(true);
  await setup.getByRole("link", { name: "Security settings", exact: true }).click();
  const executionPolicy = page.getByLabel("Shell Execution", { exact: true });
  await expect(executionPolicy).not.toBeChecked();
  await executionPolicy.click();
  await expect.poll(async () => (await (await context.request.get("/api/security")).json()).data.allowShellExecution).toBe(true);
  await expect(executionPolicy).toBeChecked();
  await page.goto("/#approvals");
  await expect(setup).toContainText("Managed sandbox runtime ready.");
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 950 });
    await setup.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await page.screenshot({ path: test.info().outputPath(`runtime-ready-${width}.png`) });
  }
  const prepared = await context.request.post("/api/execution/requests", { data: {
    workspace: process.env.RASPUTIN_RUNTIME_WORKSPACE,
    files: ["worker_fixture.cjs"], arguments: ["--preserve-symlinks", "--preserve-symlinks-main", "worker_fixture.cjs"],
  } });
  expect(prepared.ok()).toBeTruthy();
  const request = (await prepared.json()).data;
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  const card = page.locator(`[data-approval-id="${request.approvalId}"]`);
  await card.getByRole("button", { name: "Review snapshot", exact: true }).click();
  await card.getByRole("button", { name: "Approve and run snapshot", exact: true }).click();
  await expect(card.getByText("Passed", { exact: true })).toBeVisible({ timeout: 20000 });
  await expect(card).toContainText(`managed-runtime-ready ${manifest.version}`);
  expect(errors).toEqual([]);
});
