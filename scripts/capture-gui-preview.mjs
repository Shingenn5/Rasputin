import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const baseUrl = process.env.RASPUTIN_TEST_BASE_URL || "http://127.0.0.1:8899";
const outputRoot = "test-results/gui-preview";
const variants = ["warmind-console", "operator-desk", "archive-studio", "rasputin-candidate"];
const screens = ["home", "workspaces", "activity", "models", "warsat", "settings", "panels"];
const viewports = [
  ["desktop", { width: 1440, height: 1100 }],
  ["mobile", { width: 390, height: 900 }],
];

mkdirSync(outputRoot, { recursive: true });

const browser = await chromium.launch();
try {
  for (const [viewportName, viewport] of viewports) {
    const page = await browser.newPage({ viewport });
    for (const variant of variants) {
      const folder = `${outputRoot}/${variant}`;
      mkdirSync(folder, { recursive: true });
      for (const screen of screens) {
        await page.goto(`${baseUrl}/preview/${screen}`, { waitUntil: "networkidle" });
        await page.locator("[data-testid='gui-preview-variant-select']").selectOption(variant);
        await page.locator("[data-testid='gui-preview-theme-select']").selectOption("rasputin-dark");
        await page.locator("[data-testid='gui-preview-viewport-select']").selectOption(viewportName);
        await page.locator("[data-testid='gui-preview-view']").waitFor({ state: "visible" });
        await page.screenshot({ path: `${folder}/${viewportName}-${screen}.png`, fullPage: true });
      }
    }
    await page.close();
  }
} finally {
  await browser.close();
}

console.log(`Captured GUI preview screenshots in ${outputRoot}`);
