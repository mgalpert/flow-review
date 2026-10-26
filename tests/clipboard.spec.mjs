import { toolbarClick } from './toolbar.mjs';
import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

async function open(page) {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.locator('#addNote').click();
  await page.getByRole('textbox', { name: 'Canvas note', exact: true }).fill('Demo feedback: café and 你好.');
}

async function downloadFeedback(page, info) {
  const downloading = page.waitForEvent('download');
  await toolbarClick(page,'#save');
  const file = info.outputPath('feedback.json');
  await (await downloading).saveAs(file);
  return JSON.parse(await readFile(file, 'utf8'));
}

test('copied JSON matches the download and round-trips the latest review', async ({ page }, info) => {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await open(page);
  await page.locator('#commentMode').click();
  await page.locator('#world > .node[data-id=welcome] .frame-wrap').click({ position: { x: 80, y: 80 } });
  await page.getByRole('textbox', { name: 'Screen comment', exact: true }).fill('Demo comment: keep the welcome screen.');
  await page.locator('#world .comment-card .resolve-note').check();
  await page.getByRole('button', { name: 'Copy feedback', exact: true }).click({ timeout: 5000 });
  await expect(page.getByRole('status')).toContainText('Feedback JSON copied');
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const model = JSON.parse(copied);
  expect(model.format).toBe('flow-review-feedback');
  expect(Number.isNaN(Date.parse(model.exportedAt))).toBe(false);
  const downloaded = await downloadFeedback(page, info);
  delete model.exportedAt; delete downloaded.exportedAt;
  expect(model).toEqual(downloaded);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.locator('#file').setInputFiles({ name: 'copied.json', mimeType: 'application/json', buffer: Buffer.from(copied) });
  await expect(page.getByRole('textbox', { name: 'Canvas note', exact: true })).toHaveValue('Demo feedback: café and 你好.');
  await expect(page.getByRole('textbox', { name: 'Screen comment', exact: true })).toHaveValue('Demo comment: keep the welcome screen.');
  await expect(page.locator('#world .comment-card .resolve-note')).toBeChecked();
});

for (const unavailable of ['denied', 'missing']) {
  test(`clipboard ${unavailable} preserves feedback and keeps JSON download available`, async ({ page }, info) => {
    await page.addInitScript(mode => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: mode === 'missing' ? undefined : {
        writeText: async () => { throw new DOMException('Clipboard denied for test', 'NotAllowedError'); }
      } });
    }, unavailable);
    await open(page);
    await page.getByRole('button', { name: 'Copy feedback', exact: true }).click({ timeout: 5000 });
    await expect(page.getByRole('status')).toContainText('Use Export feedback to download JSON');
    await expect(page.getByRole('textbox', { name: 'Canvas note', exact: true })).toHaveValue('Demo feedback: café and 你好.');
    const downloaded = await downloadFeedback(page, info);
    expect(downloaded.annotations[0].text).toBe('Demo feedback: café and 你好.');
  });
}

test('copy feedback is visible and works at a mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/');
  await page.locator('#toggleSidebar').click();
  const button = page.locator('header').getByRole('button', { name: 'Copy feedback', exact: true });
  await expect(button).toBeInViewport({ timeout: 5000 });
  await button.click();
  await expect(page.getByRole('status')).toContainText('Feedback JSON copied');
  expect(JSON.parse(await page.evaluate(() => navigator.clipboard.readText())).format).toBe('flow-review-feedback');
});
