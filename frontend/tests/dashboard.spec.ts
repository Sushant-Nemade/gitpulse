import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

test.beforeEach(async ({ page }) => {
  await page.route('https://fonts.googleapis.com/**', route => route.abort());
  await page.route('https://fonts.gstatic.com/**', route => route.abort());
  await page.goto('/');
  await expect(page.locator('#source')).toHaveText('Sample data');
});

test('dashboard is framed and chart is nonblank', async ({ page }, testInfo) => {
  await expect(page.locator('h1')).toHaveText('GitPulse');
  await expect(page.locator('.metric')).toHaveCount(4);
  const pixels = await page.locator('canvas').evaluate(canvas => {
    const context = (canvas as HTMLCanvasElement).getContext('2d')!;
    return [...context.getImageData(0, 0, 100, 100).data].filter((value, index) => index % 4 === 3 && value > 0).length;
  });
  expect(pixels).toBeGreaterThan(10);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('overview.png'), fullPage: true });
});

test('all views, search, sorting and history', async ({ page }) => {
  await page.locator('[data-view="following"]').click();
  await expect(page.locator('#sort option:checked')).toHaveText('GitHub response order');
  for (const view of ['followers', 'following', 'lost', 'events', 'repositories']) {
    await page.locator(`[data-view="${view}"]`).click();
    await expect(page.locator('tbody tr').first()).toBeVisible();
  }
  await page.locator('[data-view="followers"]').click();
  await page.locator('#search').fill('no-match-found');
  await expect(page.locator('#results')).toContainText('No matching records');
  await page.locator('#search').fill('analyst');
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.locator('#sort').selectOption('name');
  await expect(page.locator('tbody')).toContainText('sample-analyst');
});

test('CSV export and connection validation', async ({ page }) => {
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  expect((await download).suggestedFilename()).toBe('gitpulse-followers.csv');
  await page.getByRole('button', { name: 'API connection' }).click();
  await page.locator('#server').fill('http://untrusted.invalid');
  await page.locator('#token').fill('synthetic-test-only-not-a-real-key');
  await page.getByRole('button', { name: 'Connect', exact: true }).click();
  await expect(page.locator('#notice')).toContainText('HTTPS');
});

test('injected repository names remain text', async ({ page }) => {
  await page.route('**/demo-*.json', async route => {
    const report = JSON.parse(readFileSync('src/demo.json', 'utf8'));
    report.repositories[0].name = '<img src=x onerror="window.injected=1">';
    await route.fulfill({ json: report });
  });
  await page.reload();
  await expect(page.locator('#source')).toHaveText('Sample data');
  await page.locator('[data-view="repositories"]').click();
  await expect(page.locator('tbody')).toContainText('<img');
  await expect(page.locator('tbody img')).toHaveCount(0);
  expect(await page.evaluate(() => Reflect.get(window, 'injected'))).toBeUndefined();
});