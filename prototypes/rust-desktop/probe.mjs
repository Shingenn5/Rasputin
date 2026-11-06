import { chromium } from 'playwright';
import { writeFile } from 'node:fs/promises';

const [port, output, mode] = process.argv.slice(2);
let browser;
let lastError;
const started = performance.now();
while (performance.now() - started < 100_000) {
  try {
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`, { timeout: 1500 });
    break;
  } catch (error) {
    lastError = error;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
}
if (!browser) throw lastError;
let page;
while (performance.now() - started < 100_000) {
  page = browser.contexts().flatMap(context => context.pages())
    .find(candidate => /^http:\/\/(127\.0\.0\.1|localhost):\d+/.test(candidate.url()));
  if (page) break;
  await new Promise(resolve => setTimeout(resolve, 100));
}
if (!page) throw new Error('No Rasputin WebView found');
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.locator("body[data-ready='true']").waitFor({ timeout: 90_000 });
const readyMs = performance.now() - started;
const readyEpochMs = Date.now();
const initialUrl = page.url();
const response = await page.request.get(new URL('/api/ui/bootstrap', initialUrl).href);
if (!response.ok()) throw new Error(`Desktop bootstrap failed: ${response.status()}`);
await page.keyboard.press('Tab');
const focus = await page.evaluate(() => ({
  tag: document.activeElement?.tagName,
  name: document.activeElement?.getAttribute('aria-label') || document.activeElement?.textContent?.slice(0, 60),
}));
if (!focus.tag || ['BODY', 'HTML'].includes(focus.tag)) throw new Error('Keyboard focus did not reach a control');
const button = page.getByRole('button').filter({ visible: true }).first();
await button.click();
await page.keyboard.press('Escape');
let navigationChecks;
if (mode === 'extended') {
  await page.getByTestId('nav-settings').click();
  await page.getByRole('heading', { name: 'Preferences', exact: true }).waitFor();
  const chat = page.getByTestId('nav-chat');
  await chat.focus();
  await page.keyboard.press('Enter');
  await page.waitForURL('**/#chat');
  const count = browser.contexts().flatMap(context => context.pages()).length;
  await page.evaluate(() => { window.open('https://example.invalid/prototype-blocked'); });
  await new Promise(resolve => setTimeout(resolve, 200));
  if (browser.contexts().flatMap(context => context.pages()).length !== count) {
    throw new Error('External popup was not blocked');
  }
  await page.evaluate(() => { location.href = 'https://example.invalid/prototype-blocked'; }).catch(() => {});
  await new Promise(resolve => setTimeout(resolve, 200));
  if (new URL(page.url()).origin !== new URL(initialUrl).origin) {
    throw new Error('External navigation was not blocked');
  }
  navigationChecks = { settings_mouse: true, chat_keyboard: true, external_popup_blocked: true, external_navigation_blocked: true };
}
await page.screenshot({ path: `${output}.png` });
await writeFile(output, JSON.stringify({
  ready_ms_from_probe_start: readyMs, ready_epoch_ms: readyEpochMs, bootstrap_status: response.status(),
  title: await page.title(), keyboard_focus: focus, mouse_click: true, page_errors: errors,
  navigation_checks: navigationChecks,
  browser_version: browser.version(),
  note: 'CDP is enabled only for this measurement; startup uses a fresh store and profile',
}, null, 2));
// CDP disconnect must not close the app; the parent benchmark owns shutdown.
process.exit(errors.length ? 1 : 0);
