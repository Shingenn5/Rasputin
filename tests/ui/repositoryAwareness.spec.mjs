import { expect, test } from "@playwright/test";

async function waitForAppReady(page) {
  await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
}

test("task Changes shows repository state and keeps Revert approval-gated", async ({ page, request }) => {
  const objective = `Repository awareness ${Date.now()}`;
  const createdResponse = await request.post("/api/tasks", {
    data: {
      objective,
      model: "dry-run",
      skill: "general",
      mode: "chat",
      workspacePath: ".",
    },
  });
  const created = await createdResponse.json();
  expect(created.ok).toBe(true);

  await expect.poll(async () => {
    const response = await request.get(`/api/tasks/${created.data.id}`);
    const payload = await response.json();
    return payload?.data?.task?.status;
  }, { timeout: 30000 }).toBe("done");

  await page.route("**/api/workspace/git-status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          entries: [{ status: "M", path: "tracked.txt" }],
          repository: {
            isRepository: true,
            branch: "feature/github-foundation",
            upstream: "origin/feature/github-foundation",
            ahead: 2,
            behind: 1,
            detached: false,
            headSha: "0123456789abcdef0123456789abcdef01234567",
            githubRepository: "example/rasputin",
            remotes: [{
              name: "origin",
              url: "https://github.com/example/rasputin.git",
              githubRepository: "example/rasputin",
            }],
          },
        },
        error: null,
      }),
    });
  });
  await page.route("**/api/workspace/git-restore", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: { approvalId: "approval_test_git_restore" },
        error: null,
      }),
    });
  });

  await page.goto("/");
  await waitForAppReady(page);
  await page.locator("[data-testid='nav-activity']").click();
  await page.getByRole("button", { name: "All Runs" }).click();
  await page.getByRole("textbox", { name: "Search by ID, agent, status, or error text…" }).fill(objective);
  await page.getByRole("button", { name: "Inspect" }).click();
  await page.getByRole("button", { name: "Open Full Details View" }).click();
  await page.getByRole("tab", { name: "Changes" }).click();

  const summary = page.locator("[data-testid='repository-summary']");
  await expect(summary).toContainText("feature/github-foundation");
  await expect(summary).toContainText("2 ahead / 1 behind");
  await expect(summary).toContainText("example/rasputin");
  await expect(summary).toContainText("0123456789ab");

  await page.getByRole("button", { name: "Revert tracked.txt" }).click();
  await expect(page.locator("[data-testid='task-changes']").getByRole("status")).toContainText(
    "needs approval",
  );
});
