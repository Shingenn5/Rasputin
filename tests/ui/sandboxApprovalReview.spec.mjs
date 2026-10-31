import { expect, test } from "@playwright/test";

test("operator reviews captured bytes, approves real execution, denies, stops, and respects output ownership", async ({ page, context, browser }) => {
  test.skip(!process.env.RASPUTIN_REVIEW_FIXTURES, "Requires the isolated live sandbox review harness");
  test.setTimeout(120000);
  const fixtures = JSON.parse(process.env.RASPUTIN_REVIEW_FIXTURES);
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const login = await context.request.post("/api/auth/login", { data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD } });
  expect(login.ok()).toBeTruthy();
  const onboarded = await context.request.post("/api/preferences", { data: { onboarded: true } });
  expect(onboarded.ok()).toBeTruthy();
  await page.addInitScript(() => localStorage.setItem("rasputin-onboarded", "1"));
  await page.goto("/#approvals");
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });

  const card = id => page.locator(`[data-approval-id="${id}"]`);
  const passing = card(fixtures.passing.approvalId);
  await expect(passing).toBeVisible();
  await expect(passing.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  const disclosure = passing.getByRole("button", { name: "Review snapshot", exact: true });
  await disclosure.focus();
  await page.keyboard.press("Enter");
  await expect(passing.getByRole("heading", { name: "Exact arguments" })).toBeVisible();
  const inspect = passing.getByRole("button", { name: /worker_fixture.cjs.*bytes/ });
  await inspect.focus();
  await page.keyboard.press("Enter");
  const captured = passing.getByRole("region", { name: "Captured file: worker_fixture.cjs" });
  await expect(captured).toContainText("captured-version-marker");
  await expect(captured).not.toContainText("later-source-version");
  await expect(page.locator('img[src="snapshot-xss"]')).toHaveCount(0);
  await expect(passing.getByRole("list", { name: "Exact runtime arguments" }).locator("li")).toHaveCount(4);
  await expect(passing.getByRole("list", { name: "Exact runtime arguments" }).locator("li").first()).toHaveText('"--preserve-symlinks"');

  for (const width of [1440, 1024, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `page overflow at ${width}px`).toBeLessThanOrEqual(1);
    const approveAction = passing.getByRole("button", { name: "Approve and run snapshot", exact: true });
    await expect(approveAction).toBeVisible();
    await approveAction.scrollIntoViewIfNeeded();
    await page.screenshot({ path: test.info().outputPath(`review-${width}.png`), fullPage: true });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  const approve = passing.getByRole("button", { name: "Approve and run snapshot", exact: true });
  await approve.focus();
  await page.keyboard.press("Enter");
  await expect(passing.getByText("Passed", { exact: true })).toBeVisible({ timeout: 20000 });
  await expect(passing.getByText("captured-version-marker", { exact: true })).toBeVisible();
  const saved = await context.request.get(`/api/execution/requests/${fixtures.passing.requestId}`);
  expect((await saved.json()).data.receipt.passed).toBe(true);

  const denied = card(fixtures.denied.approvalId);
  await denied.getByRole("button", { name: "Review snapshot", exact: true }).click();
  await denied.getByRole("button", { name: "Deny snapshot", exact: true }).click();
  await expect(denied.locator(".sandbox-review-status")).toHaveText("Denied");

  const slow = card(fixtures.slow.approvalId);
  await slow.getByRole("button", { name: "Review snapshot", exact: true }).click();
  await slow.getByRole("button", { name: "Approve and run snapshot", exact: true }).click();
  await slow.getByRole("button", { name: "Stop execution", exact: true }).click();
  await expect(slow.getByRole("button", { name: "Stop execution", exact: true })).toHaveCount(0, { timeout: 20000 });
  const stopped = await context.request.get(`/api/execution/requests/${fixtures.slow.requestId}`);
  expect((await stopped.json()).data.receipt.passed).toBe(false);
  await expect(slow.locator(".sandbox-review-status")).not.toHaveText("Passed");

  const foreign = card(fixtures.foreign.approvalId);
  await foreign.getByRole("button", { name: "Review snapshot", exact: true }).click();
  await expect(foreign.getByRole("button", { name: "Approve and run snapshot", exact: true })).toHaveCount(0);
  await foreign.getByRole("button", { name: "Approve snapshot", exact: true }).click();
  const member = await browser.newContext({ baseURL: process.env.RASPUTIN_TEST_BASE_URL });
  try {
    const memberLogin = await member.request.post("/api/auth/login", { data: { username: "reviewmember", password: process.env.RASPUTIN_TEST_MEMBER_PASSWORD } });
    expect(memberLogin.ok()).toBeTruthy();
    const executed = await member.request.post(`/api/execution/requests/${fixtures.foreign.requestId}/execute`, { data: {} });
    expect(executed.ok()).toBeTruthy();
    expect((await executed.json()).data.passed).toBe(true);
    await expect(foreign.getByText("Execution output is private to the request owner.", { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(foreign).not.toContainText("foreign-private-output");
  } finally { await member.close(); }
  expect(errors).toEqual([]);
});
