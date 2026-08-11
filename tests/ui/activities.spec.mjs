import { test, expect } from '@playwright/test';

test.describe('Activities V2 Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator("body")).toHaveAttribute("data-ready", "true", { timeout: 60000 });
    await page.locator("[data-testid='nav-activity']").click();
  });

  test('should render Activity Center header and stats', async ({ page }) => {
    await expect(page.locator('h1', { hasText: 'Activity Center' })).toBeVisible();
    await expect(page.getByText('Unread', { exact: true })).toBeVisible();
    await expect(page.getByText('Successes', { exact: true })).toBeVisible();
  });

  test('should navigate tabs correctly', async ({ page }) => {
    // Audit Log Tab
    await page.click('button:has-text("Audit Log")');
    await expect(page.locator('h2', { hasText: 'Action Registry & Audit Log' })).toBeVisible();

    // System Events Tab
    await page.click('button:has-text("System Events")');
    await expect(page.locator('h2', { hasText: 'System Health Panel' })).toBeVisible();
    await expect(page.locator('text=API Status')).toBeVisible();

    // Active Runs Tab
    await page.locator("#activityView").getByRole("button", { name: "Active", exact: true }).click();
    const searchInput = page.locator('input[placeholder*="Search by ID"]');
    await expect(searchInput).toBeVisible();
  });

  test('should register button interactions via actionRegistry', async ({ page }) => {
    await page.click('button:has-text("Audit Log")');
    
    // Switch to Workspaces and trigger a governed action to log it.
    await page.locator("[data-testid='nav-workspaces']").click();
    await page.getByRole('button', { name: 'Index Workspace' }).click();

    // Switch back to Activity -> Audit Log and verify entry.
    await page.locator("[data-testid='nav-activity']").click();
    
    await page.click('button:has-text("Audit Log")');
    
    // The action should be logged as a success or at least started
    // We expect the reliable action wrapper to generate an audit log entry
    // Wait for the UI state readout or log entries
    const logs = page.locator('.w2-card > div');
    await expect(logs).not.toHaveCount(0);
  });
});
