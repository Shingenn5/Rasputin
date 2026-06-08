import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";

test.skip(process.env.RASPUTIN_GUI_PREVIEW !== "1", "GUI preview tests run only in RasputinTest preview mode.");

const screenshotRoot = "test-results/gui-preview";

test.beforeAll(() => {
  mkdirSync(screenshotRoot, { recursive: true });
  for (const variant of ["warmind-console", "operator-desk", "archive-studio"]) {
    mkdirSync(`${screenshotRoot}/${variant}`, { recursive: true });
  }
});

test("RasputinTest preview routes, variants, themes, and viewport presets render", async ({ page }) => {
  await page.goto("/preview/home");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true");
  await expect(page.locator("[data-testid='gui-preview-view']")).toBeVisible();
  await expect(page.locator("text=GUI Preview Hub")).toBeVisible();

  for (const [route, label] of [
    ["/preview/home", "Home"],
    ["/preview/workspaces", "Workspaces"],
    ["/preview/activity", "Activity"],
    ["/preview/models", "Models"],
    ["/preview/warsat", "Warsat"],
    ["/preview/settings", "Settings"],
    ["/preview/panels", "Panels"],
  ]) {
    await page.goto(route);
    await expect(page.locator(".preview-header h2")).toHaveText(label);
  }

  await page.locator("[data-testid='gui-preview-screen-select']").selectOption("workspaces");
  await expect(page).toHaveURL(/\/preview\/workspaces$/);
  await expect(page.locator("text=Approved folders")).toBeVisible();

  for (const [variant, label] of [
    ["warmind-console", "Warmind Console"],
    ["operator-desk", "Operator Desk"],
    ["archive-studio", "Archive Studio"],
  ]) {
    await page.locator("[data-testid='gui-preview-variant-select']").selectOption(variant);
    await expect(page.locator(".preview-brand small")).toHaveText(label);
    await page.screenshot({ path: `${screenshotRoot}/${variant}/workspaces.png`, fullPage: true });
  }

  await page.locator("[data-testid='gui-preview-theme-select']").selectOption("bootswatch-lux");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "bootswatch-lux");

  await page.locator("[data-testid='gui-preview-viewport-select']").selectOption("mobile");
  await expect(page.locator(".preview-stage")).toHaveAttribute("data-viewport", "mobile");

  const overflow = await page.evaluate(() => {
    return Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth;
  });
  expect(overflow).toBeLessThanOrEqual(4);

  await expect(page.locator("[data-testid='gui-preview-accessibility-checks']")).toContainText("Keyboard path");
});
