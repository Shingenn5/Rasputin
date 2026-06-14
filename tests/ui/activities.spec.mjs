import { test, expect } from '@playwright/test';

test.describe('Activities V2 Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Activities view
    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('rasputin:navigate', { detail: { view: 'activity' } }));
    });
  });

  test('should render Activities Center header and stats', async ({ page }) => {
    await expect(page.locator('h1', { hasText: 'Activities Center' })).toBeVisible();
    await expect(page.locator('text=Total Runs')).toBeVisible();
    await expect(page.locator('text=Successes')).toBeVisible();
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
    await page.click('button:has-text("Active")');
    const searchInput = page.locator('input[placeholder*="Search by ID"]');
    await expect(searchInput).toBeVisible();
  });

  test('should register button interactions via actionRegistry', async ({ page }) => {
    await page.click('button:has-text("Audit Log")');
    
    // Switch to Workspaces and trigger an action to log it
    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('rasputin:navigate', { detail: { view: 'workspaces' } }));
    });
    
    // Click Add Folder Workflow
    await page.click('button:has-text("Add Folder Workflow")');
    
    // Switch back to Activity -> Audit Log and verify entry
    await page.evaluate(() => {
      window.dispatchEvent(new CustomEvent('rasputin:navigate', { detail: { view: 'activity' } }));
    });
    
    await page.click('button:has-text("Audit Log")');
    
    // The action should be logged as a success or at least started
    // We expect the reliable action wrapper to generate an audit log entry
    // Wait for the UI state readout or log entries
    const logs = page.locator('.w2-card > div');
    await expect(logs).not.toHaveCount(0);
  });
});
