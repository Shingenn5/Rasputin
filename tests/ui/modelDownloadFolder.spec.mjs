import { expect, test } from "@playwright/test";
import path from "node:path";

test("download folder saves, survives reload, validates paths, and resets at all widths", async ({ page, context }, testInfo) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD || !process.env.RASPUTIN_FOLDER_QA_ROOT, "Requires an isolated QA server");
  const login = await context.request.post("/api/auth/login", {
    data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  const preferences = await context.request.post("/api/preferences", { data: { onboarded: true, activeView: "models" } });
  expect(preferences.ok()).toBeTruthy();
  await page.addInitScript(() => localStorage.setItem("rasputin-onboarded", "1"));
  const target = path.join(process.env.RASPUTIN_FOLDER_QA_ROOT, "Models on another drive", "long folder name for responsive verification");
  await page.goto("/#models");
  const panel = page.getByTestId("model-download-folder");
  await expect(panel.locator("summary span")).not.toBeEmpty();
  await panel.locator("summary").focus();
  await page.keyboard.press("Enter");
  await panel.getByRole("textbox", { name: "Model download folder" }).fill(target);
  await panel.getByRole("button", { name: "Save folder" }).click();
  await expect(panel.getByRole("status")).toContainText("Download folder saved");
  await page.reload();
  await expect(panel.locator("summary")).toContainText(target);
  await panel.locator("summary").click();
  await panel.getByRole("textbox").fill("relative/folder");
  await panel.getByRole("button", { name: "Save folder" }).click();
  await expect(panel.getByRole("alert")).toContainText("absolute folder path");
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(panel.getByRole("textbox")).toBeVisible();
    const bounds = await panel.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
    expect(await panel.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`download-folder-${width}.png`) });
  }
  await panel.getByRole("button", { name: "Use default" }).click();
  await expect(panel.getByRole("status")).toContainText("Download folder saved");
  await expect(panel.locator("summary")).not.toContainText(target);
  await page.getByRole("tab", { name: "Discover", exact: false }).click();
  await expect(panel).toBeVisible();
});
