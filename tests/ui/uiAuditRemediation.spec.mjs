import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page, context }) => {
  test.skip(!process.env.RASPUTIN_TEST_PASSWORD, "Requires an isolated authenticated server");
  const login = await context.request.post("/api/auth/login", {
    data: { username: "admin", password: process.env.RASPUTIN_TEST_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  await context.request.post("/api/preferences", { data: { onboarded: true, motionMode: "system", activeView: "chat" } });
  await page.addInitScript(() => {
    localStorage.setItem("rasputin-theme", "rasputin-dark");
    localStorage.setItem("rasputin-theme-explicit", "1");
  });
});

test("settings, skills and schedules expose meaningful control names", async ({ page }) => {
  await page.goto("/#settings/general");
  for (const label of ["Platform Theme", "Interface Language", "Interface Motion", "Default Workspace Path", "Markdown Formatting", "Testing Mode"]) {
    await expect(page.getByLabel(label, { exact: true })).toBeVisible();
  }
  const markdown = page.getByLabel("Markdown Formatting", { exact: true });
  const checked = await markdown.isChecked();
  await page.locator('label[for="markdown-switch"]').click();
  await expect(markdown).toBeChecked({ checked: !checked });
  await page.goto("/#skills");
  await expect(page.getByRole("combobox", { name: "Save workflow from session" })).toBeVisible();
  await page.goto("/#schedules");
  await expect(page.getByRole("spinbutton", { name: "Interval seconds" })).toBeVisible();
  await expect(page.getByLabel("Enabled", { exact: true })).toBeVisible();
});

test("system motion responds to OS changes and explicit choices survive reload", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/#settings/general");
  const motion = page.getByRole("combobox", { name: "Interface Motion" });
  await expect(motion).toHaveValue("system");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await motion.selectOption("full");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "full");
  await page.reload();
  await expect(motion).toHaveValue("full");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "full");
  await motion.selectOption("system");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(page.locator("html")).toHaveAttribute("data-motion", "full");
  await motion.selectOption("reduced");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await page.goto("/#skills");
  await expect(page.locator("#skillsView")).toHaveCSS("animation-name", "none");
  await expect(page.locator("#skillsView .ras-runtime-orbit, #skillsView .ras-runtime-kicker")).toHaveCount(0);
});

test("narrow dashboard scrolling has a visible keyboard path and folder actions stay outside the tree", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#home");
  const region = page.getByRole("region", { name: "Top models usage table" });
  await region.focus();
  await expect(region).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => region.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  await page.keyboard.press("Tab");
  await expect(region).not.toBeFocused();
  await page.goto("/#discover");
  const details = page.getByRole("region", { name: "Model discovery details" });
  await details.focus();
  await expect(details).toBeFocused();
  // The expanded page can scroll at its outer container rather than clipping
  // the details region. Exercise whichever real scrollbar contains the focus.
  const scrollContainer = await details.evaluateHandle((element) => {
    for (let node = element; node; node = node.parentElement) {
      if (node.scrollHeight > node.clientHeight && /auto|scroll/.test(getComputedStyle(node).overflowY)) return node;
    }
    return document.scrollingElement;
  });
  const scroll = await scrollContainer.evaluate(element => ({ top: element.scrollTop, max: element.scrollHeight - element.clientHeight }));
  if (scroll.max > 0) {
    await page.keyboard.press(scroll.top < scroll.max ? "ArrowDown" : "ArrowUp");
    await expect.poll(() => scrollContainer.evaluate(element => element.scrollTop)).not.toBe(scroll.top);
  } else {
    expect(await details.evaluate(element => element.scrollHeight <= element.clientHeight)).toBe(true);
  }
  await page.keyboard.press("Tab");
  await expect(details).not.toBeFocused();
  await page.goto("/#workspaces");
  await expect(page.locator('[role="tree"] .workspace-add-folder')).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Open Project", exact: true }).last()).toBeVisible();
});

test("primary action text remains readable across themes and interaction states", async ({ page }) => {
  await page.goto("/#home");
  const action = page.getByTestId("dashboard-open-assistant");
  async function contrast() {
    return action.evaluate((element) => {
      const context = document.createElement("canvas").getContext("2d");
      function luminance(color) {
        context.clearRect(0, 0, 1, 1);
        context.fillStyle = color;
        context.fillRect(0, 0, 1, 1);
        const channels = [...context.getImageData(0, 0, 1, 1).data].slice(0, 3)
          .map((value) => value / 255)
          .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
        return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
      }
      const style = getComputedStyle(element);
      const a = luminance(style.color), b = luminance(style.backgroundColor);
      return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    });
  }
  for (const theme of ["rasputin-dark", "rasputin-light"]) {
    await page.evaluate((value) => window.rasputinTheme.apply(value), theme);
    await page.mouse.move(0, 0);
    await expect.poll(contrast).toBeGreaterThanOrEqual(4.5);
    await action.hover();
    await expect.poll(contrast).toBeGreaterThanOrEqual(4.5);
    await action.focus();
    await expect.poll(contrast).toBeGreaterThanOrEqual(4.5);
    await action.blur();
  }
});

test("deferred models retain filters after navigating away", async ({ page }) => {
  await page.goto("/#models");
  const filter = page.getByLabel("Filter installed models");
  await filter.fill("retained filter");
  await page.goto("/#chat");
  await page.goto("/#models");
  await expect(filter).toHaveValue("retained filter");
});

test("a failed secondary-page download leaves a recovery action and working navigation", async ({ page }) => {
  await page.route("**/assets/SettingsView-*.js", (route) => route.abort());
  await page.goto("/#chat");
  await expect(page.locator("#objective")).toBeVisible();
  await page.goto("/#settings/general");
  await expect(page.getByRole("alert")).toContainText("This page could not load");
  await expect(page.getByRole("button", { name: "Reload application" })).toBeVisible();
  await page.goto("/#chat");
  await expect(page.locator("#objective")).toBeVisible();
});
