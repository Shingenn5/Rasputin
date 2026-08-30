import test from "node:test";
import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";

// Run only against an explicitly selected isolated native test server.
// RASPUTIN_TEST_BASE_URL + RASPUTIN_TEST_ADMIN_PASSWORD enable this browser gate.
const baseURL = process.env.RASPUTIN_TEST_BASE_URL;
const password = process.env.RASPUTIN_TEST_ADMIN_PASSWORD;
const fixtureModel = {
  key: "native-dialog-fixture", name: "Native dialog fixture", model: "fixture.gguf",
  provider: "llamacpp", runtime: "native-llamacpp", enabled: true, managed: true,
  host_model_path: "C:/isolated-fixture/fixture.gguf", runtimeStatus: "stopped", role: "helper",
};

test("native onboarding owns focus, reaches Discover, and preserves nested Load keyboard controls", {
  skip: !baseURL || !password,
  timeout: 120000,
}, async () => {
  const url = new URL(baseURL);
  assert.ok(["127.0.0.1", "localhost"].includes(url.hostname), "Use an isolated local test server");
  const browser = await chromium.launch();
  try {
    for (const desktopOnly of [false, true]) {
      const context = await browser.newContext({ baseURL, viewport: { width: 1366, height: 900 } });
      try {
        const login = await context.request.post("/api/auth/login", {
          data: { username: "admin", password },
        });
        assert.equal(login.ok(), true, "Isolated server login succeeds");
        const page = await context.newPage();
        let modelState = { ...fixtureModel };
        const errors = [];
        const retiredRequests = [];
        page.on("pageerror", (error) => errors.push(error.message));
        page.on("request", (request) => {
          if (/\/api\/warsat\/(plan|protocols|runtimes)/.test(request.url())) retiredRequests.push(request.url());
        });
        await page.route("**/api/ui/bootstrap", async (route) => {
          const response = await route.fetch();
          const json = await response.json();
          json.data.security = { ...json.data.security, native: true, desktopOnly };
          json.data.models = [modelState];
          await route.fulfill({ json });
        });
        await page.route(/\/api\/model-registry(?:\?.*)?$/, (route) => route.fulfill({
          json: { ok: true, data: { models: [modelState] } },
        }));
        await page.route("**/api/model-registry/start", (route) => {
          modelState = { ...modelState, containerStatus: "running", runtimeStatus: "reachable" };
          return route.fulfill({ json: { ok: true, data: { ok: true } } });
        });
        await page.route("**/api/model-registry/stop", (route) => {
          modelState = { ...modelState, containerStatus: "stopped", runtimeStatus: "stopped", lastHealth: { status: "reachable" } };
          return route.fulfill({ json: { ok: true, data: { ok: true } } });
        });
        await page.route("**/api/model-catalog/search?**", (route) => route.fulfill({
          json: { ok: true, data: { items: [], count: 0 } },
        }));
        await page.route("**/api/model-catalog/load-plan-preview", (route) => route.fulfill({
          json: { ok: true, data: { accepted: true, blocked: false, resolvedSettings: {} } },
        }));
        await page.goto("/#warsat");
        await page.waitForSelector('body[data-ready="true"]');
        await expect(page.getByRole("dialog")).toHaveCount(1);
        const welcome = page.getByRole("dialog", { name: "Welcome to Rasputin" });
        await expect(welcome).toBeVisible();
        await expect(welcome).not.toContainText(/containers|WarSat/);
        await welcome.getByRole("button", { name: "Skip for now" }).click();
        await expect(page.locator("#appFrame")).toHaveAttribute("data-current-view", "models");
        await expect(page).toHaveURL(/#models$/);
        await expect(page.locator("aside").getByRole("button", { name: "WarSat", exact: true })).toHaveCount(0);

        // A later history navigation must also replace the retired hash.
        await page.evaluate(() => { window.location.hash = "settings/security"; });
        await expect(page.getByTestId("native-runtime-row")).toBeVisible();
        await expect(page.locator("#allow-docker-control")).toHaveCount(0);
        await page.evaluate(() => { window.location.hash = "warsat"; });
        await expect(page.locator("#appFrame")).toHaveAttribute("data-current-view", "models");
        await expect(page).toHaveURL(/#models$/);

        // Test the real first-run primary action, including keyboard activation.
        await page.evaluate(() => localStorage.removeItem("rasputin-onboarded"));
        await page.reload();
        await expect(welcome).toBeVisible();
        await welcome.getByRole("button", { name: "Get started" }).click();
        const discover = page.getByRole("dialog", { name: "Get your first model ready" }).getByRole("button", { name: "Discover Models", exact: true });
        await discover.focus();
        await page.keyboard.press("Enter");
        await expect(page.locator("#appFrame")).toHaveAttribute("data-current-view", "discover");
        await expect(page.getByRole("dialog", { name: "Get your first model ready" })).toHaveCount(0);

        if (desktopOnly) {
          await page.evaluate(() => { window.location.hash = "models"; });
          const row = page.locator('[data-model-key="native-dialog-fixture"]');
          await row.getByRole("button", { name: "Load", exact: true }).click();
          const loadDialog = page.locator(".studio-load-modal");
          await expect(loadDialog).toBeVisible();
          await expect(loadDialog.getByRole("button", { name: "Load model", exact: true })).toBeEnabled();
          await loadDialog.getByRole("button", { name: "Close dialog", exact: true }).focus();
          const targets = [];
          for (let tab = 0; tab < 4; tab += 1) {
            await page.keyboard.press("Tab");
            const focus = await page.evaluate(() => ({
              inside: Boolean(document.activeElement?.closest(".studio-load-modal")),
              label: document.activeElement?.getAttribute("aria-label") || document.activeElement?.textContent,
            }));
            assert.equal(focus.inside, true, "Tab stays in the Load dialog");
            targets.push(focus.label);
          }
          assert.ok(new Set(targets).size > 1, "Tab advances beyond one element");
          await page.keyboard.press("Escape");
          await expect(loadDialog).toHaveCount(0);
          await expect(page.getByTestId("desktop-models-dialog")).toBeVisible();
          await expect(page.locator("#appFrame")).toHaveAttribute("data-current-view", "models");
          await row.getByRole("button", { name: "Load", exact: true }).click();
          await loadDialog.getByRole("button", { name: "Load model", exact: true }).click();
          await expect(row.getByRole("button", { name: "Stop", exact: true })).toBeVisible();
          await expect(page.getByTestId("installed-model-inspector").getByRole("button", { name: "Stop Model", exact: true })).toBeVisible();
          await expect(page.getByText("1 reachable · 1 loaded", { exact: true })).toBeVisible();
          await row.getByRole("button", { name: "Stop", exact: true }).click();
          await expect(row.getByRole("button", { name: "Load", exact: true })).toBeVisible();
          await expect(page.getByText("0 reachable · 0 loaded", { exact: true })).toBeVisible();
        }
        assert.deepEqual(retiredRequests, [], "Native routes must not request retired deployment APIs");
        assert.deepEqual(errors, [], "No unhandled browser errors");
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
});
