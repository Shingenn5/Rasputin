import test from "node:test";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium, expect } from "@playwright/test";

// Fixture evidence only: the production API runs a dry-run model on isolated data.
const baseURL = process.env.RASPUTIN_TEST_BASE_URL;
const password = process.env.RASPUTIN_TEST_ADMIN_PASSWORD;

test("Trials scorecards distinguish measured request completion from unmeasured quality", {
  skip: !baseURL || !password,
  timeout: 120000,
}, async () => {
  const url = new URL(baseURL);
  assert.ok(["127.0.0.1", "localhost"].includes(url.hostname), "Use an isolated local test server");
  const browser = await chromium.launch();
  let experimentId;
  let context;
  try {
    context = await browser.newContext({ baseURL, viewport: { width: 1366, height: 1100 } });
    const login = await context.request.post("/api/auth/login", { data: { username: "admin", password } });
    assert.equal(login.ok(), true, "Isolated server login succeeds");
    async function post(endpoint, data) {
      const response = await context.request.post(endpoint, { data });
      assert.equal(response.ok(), true, `Fixture API succeeds: ${endpoint}`);
      const body = await response.json();
      assert.equal(body.ok, true);
      return body.data;
    }
    const experiment = await post("/api/trials/experiments", {
      name: "Scorecard browser fixture",
      type: "model",
      config: { prompt: "Fixture request only.", modelKeys: ["dry-run"] },
    });
    experimentId = experiment.id;
    const completed = await post(`/api/trials/experiments/${experimentId}/run`, {});
    assert.equal(completed.status, "completed");
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.addInitScript(() => localStorage.setItem("rasputin-onboarded", "1"));
    await page.goto("/#trials");
    await page.waitForSelector('body[data-ready="true"]');
    const welcome = page.getByRole("dialog", { name: "Welcome to Rasputin" });
    if (await welcome.isVisible()) await welcome.getByRole("button", { name: "Skip for now" }).click();
    await page.getByText("Scorecard browser fixture", { exact: true }).click();
    const generated = page.waitForResponse(response =>
      response.url().endsWith("/api/trials/scorecards") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Generate Scorecard", exact: true }).click();
    const generatedResponse = await generated;
    assert.equal(generatedResponse.ok(), true);
    const card = (await generatedResponse.json()).data;
    assert.equal(card.scores.reliability, 100);
    assert.equal(card.scores.accuracy, null);
    assert.equal(card.scores.overall, 100);
    const scorecard = page.getByTestId("trial-scorecard");
    await expect(scorecard).toBeVisible();
    await expect(scorecard).toContainText("1 of 7 dimensions measured");
    for (const category of ["accuracy", "reasoning", "performance", "efficiency", "safety", "usability"]) {
      await expect(page.getByTestId(`scorecard-${category}`)).toContainText("Not measured");
    }
    await expect(page.getByTestId("scorecard-reliability")).toContainText("100 / 100");
    await expect(page.getByTestId("scorecard-radar").locator("circle")).toHaveCount(1);
    await expect(page.getByTestId("scorecard-data-polygon")).toHaveCount(0);
    const details = scorecard.locator("summary");
    await details.focus();
    await page.keyboard.press("Enter");
    await expect(scorecard.locator("details")).toHaveAttribute("open", "");
    await expect(scorecard).toContainText("Samples: 1");
    await expect(scorecard).toContainText("Uncertainty: Not estimated");
    await expect(scorecard).toContainText("dry-run responses");
    await page.keyboard.press("Enter");

    const artifactDir = process.env.RASPUTIN_TEST_ARTIFACT_DIR;
    if (artifactDir) {
      await mkdir(artifactDir, { recursive: true });
      const screenshot = path.join(artifactDir, "trials-scorecard-desktop.png");
      await scorecard.screenshot({ path: screenshot });
      console.log(`Trials screenshot: ${screenshot}`);
    }
    // Exercise narrow card wrapping without changing the existing Trials page layout.
    await scorecard.evaluate(element => { element.style.width = "260px"; });
    const overflow = await scorecard.evaluate(element => element.scrollWidth > element.clientWidth + 1);
    assert.equal(overflow, false, "Scorecard content fits a narrow inspector");
    if (artifactDir) {
      const screenshot = path.join(artifactDir, "trials-scorecard-narrow.png");
      await scorecard.screenshot({ path: screenshot });
      console.log(`Trials screenshot: ${screenshot}`);
    }

    // A stale client/API card without provenance must also hide the old invented scores.
    await page.route("**/api/trials/scorecards", route => route.fulfill({
      json: { ok: true, data: [{ ...card, evidence: undefined, scores: {
        accuracy: 100, reasoning: 50, reliability: 100, performance: 95,
        efficiency: 100, safety: 85, usability: 70, overall: 86,
      } }] },
    }));
    await page.reload();
    await page.waitForSelector('body[data-ready="true"]');
    await page.getByText("Scorecard browser fixture", { exact: true }).click();
    await expect(scorecard).toContainText("0 of 7 dimensions measured");
    await expect(scorecard).toContainText("Regenerate");
    await expect(page.getByTestId("scorecard-overall")).toContainText("Not measured");
    await expect(page.getByTestId("scorecard-radar")).toHaveCount(0);
    assert.deepEqual(errors, [], "No unhandled browser errors");
  } finally {
    if (context && experimentId) await context.request.delete(`/api/trials/experiments/${experimentId}`);
    if (context) await context.close();
    await browser.close();
  }
});
