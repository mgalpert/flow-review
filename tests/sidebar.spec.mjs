import { test, expect } from '@playwright/test';

for (const width of [1440, 610, 390]) {
  test(`sidebar collapse frees canvas space and restores feedback at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 980 });
    await page.goto('/');
    await page.locator('#addNote').click();
    await page.getByRole('textbox', { name: 'Canvas note', exact: true }).fill('Demo feedback stays on the board.');
    const header = await page.locator('header').boundingBox();
    const subtitle = page.locator('header p');
    if (await subtitle.isVisible()) {
      const text = await subtitle.boundingBox();
      expect(text.y + text.height).toBeLessThanOrEqual(header.y + header.height);
    }
    const positions = await page.evaluate(() => structuredClone(wiredAPI.getModel().positions));
    const before = await page.locator('#viewport').boundingBox();
    const hide = page.getByRole('button', { name: 'Hide sidebar', exact: true });
    await expect(hide).toBeInViewport({ timeout: 5000 });
    await expect(hide).toHaveAttribute('aria-expanded', 'true');
    await hide.focus();
    await page.keyboard.press('Space');
    await expect(page.locator('aside')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Copy feedback', exact: true })).toBeInViewport();
    const after = await page.locator('#viewport').boundingBox();
    expect(after.x).toBe(0);
    expect(after.width - before.width).toBeCloseTo(210);
    const show = page.getByRole('button', { name: 'Show sidebar', exact: true });
    await expect(show).toBeInViewport();
    await expect(show).toHaveAttribute('aria-expanded', 'false');
    await show.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('aside')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Copy feedback', exact: true })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Canvas note', exact: true })).toHaveValue('Demo feedback stays on the board.');
    expect(await page.evaluate(() => wiredAPI.getModel().positions)).toEqual(positions);
    expect((await page.locator('#viewport').boundingBox()).width).toBe(before.width);
  });
}

test('More actions supports Space to open and Escape to close',async({page})=>{
  await page.goto('/');const summary=page.locator('.more-tools summary');
  await summary.focus();await page.keyboard.press('Space');
  await expect(page.getByRole('button',{name:'Export feedback',exact:true})).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button',{name:'Export feedback',exact:true})).toBeHidden();
});
