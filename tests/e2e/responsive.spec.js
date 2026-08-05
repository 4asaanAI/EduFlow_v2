const { test, expect } = require('../support/fixtures');

const WIDTHS = [320, 360, 390, 768, 1024, 1440];

test('authenticated shell remains usable without document overflow at target widths', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByTestId('app-layout')).toBeVisible();

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: width <= 390 ? 720 : 900 });
    await expect(page.getByTestId('main-header')).toBeVisible();

    const overflow = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      body: document.body.scrollWidth - document.body.clientWidth,
    }));
    expect(overflow.document, `document overflow at ${width}px`).toBeLessThanOrEqual(1);
    expect(overflow.body, `body overflow at ${width}px`).toBeLessThanOrEqual(1);

    if (width <= 768) {
      await expect(page.getByRole('button', { name: 'Open menu' })).toBeVisible();
      await page.getByRole('button', { name: 'Open menu' }).click();
      await expect(page.getByTestId('sidebar')).toBeVisible();
      await page.getByRole('button', { name: 'Close menu' }).click();
    }
  }
});
