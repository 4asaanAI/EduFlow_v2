const { test, expect } = require('../support/fixtures');

const WIDTHS = [320, 360, 390, 768, 1024, 1440];

// Owner request 20 remainder (2026-08-07). Aman asked for the same class of layout
// miss to be looked for across the WHOLE platform, not only the two places he named.
// Everything above this line checked the owner's screens; a teacher, an accountant
// and a parent are shown different screens, and nobody had ever looked at those on a
// phone. These match the usernames the E2E double now accepts.
const ROLES = ['owner', 'principal', 'accountant', 'ittech', 'management', 'teacher', 'student', 'parent'];
const PHONE = { width: 360, height: 720 };
const E2E_PASSWORD = 'admin123';

async function signInAs(page, username) {
  await page.goto('/login');
  await page.getByTestId('login-username').fill(username);
  await page.getByTestId('login-password').fill(E2E_PASSWORD);
  await page.getByTestId('login-submit').click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  await expect(page.getByTestId('app-layout')).toBeVisible();
}

async function documentOverflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

/**
 * Nothing inside the app shell may stick out sideways past the screen.
 *
 * Checked per element rather than only on the document, because the shell sets
 * `overflow-x: hidden` on html/body. That guard stops the PAGE scrolling, so a card
 * that overhangs is simply clipped and the document-level check stays clean while
 * the person loses the right-hand edge of the content. That is the failure mode the
 * owner reported for tables, and it is invisible to the older assertion.
 */
async function overhangingElements(page) {
  return page.evaluate(() => {
    const main = document.querySelector('.app-main-content');
    if (!main) return [];
    const limit = main.getBoundingClientRect().right + 1;
    const offenders = [];
    for (const el of main.querySelectorAll('*')) {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      // A region that is MEANT to scroll sideways is not an offender; its own
      // content being wider than it is is the whole point.
      const style = window.getComputedStyle(el);
      if (style.overflowX === 'auto' || style.overflowX === 'scroll') continue;
      if (rect.right > limit) {
        offenders.push(`${el.tagName.toLowerCase()}.${el.className || '(no class)'} right=${Math.round(rect.right)} limit=${Math.round(limit)}`);
      }
    }
    return offenders.slice(0, 5);
  });
}

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

test('management hubs and commercial workspace adapt across target widths', async ({ page }) => {
  await page.goto('/dashboard?tool=finance-commercial-hub');
  await expect(page.getByTestId('management-hub-finance-commercial-hub')).toBeVisible();

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: width <= 390 ? 720 : 900 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `finance hub overflow at ${width}px`).toBeLessThanOrEqual(1);
    await expect(page.getByRole('button', { name: 'Open Commercial Operations' })).toBeVisible();
  }

  await page.getByRole('button', { name: 'Open Commercial Operations' }).click();
  await expect(page.getByText('Commercial Operations', { exact: true })).toBeVisible();
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: width <= 390 ? 720 : 900 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `commercial workspace overflow at ${width}px`).toBeLessThanOrEqual(1);
  }
});

for (const role of ROLES) {
  test(`every screen offered to ${role} fits a phone`, async ({ browser }) => {
    // A fresh context, deliberately WITHOUT the saved owner session, or every role
    // would silently be checked as the owner and this whole sweep would prove nothing.
    const context = await browser.newContext({ storageState: undefined, viewport: PHONE });
    const page = await context.newPage();
    try {
      await signInAs(page, role);

      // Read the role's own menu. Hard-coding a tool list here would go stale the
      // first time the menu changes, and would quietly stop covering new screens.
      await page.getByRole('button', { name: 'Open menu' }).click();
      await expect(page.getByTestId('sidebar')).toBeVisible();

      // Teachers and students keep every screen inside a collapsed group, so the
      // tools are not in the page until each group is opened. Skipping this made the
      // first run report that a teacher is offered no screens at all.
      const groups = page.locator('[data-testid^="tool-group-"]');
      for (let i = 0; i < await groups.count(); i += 1) {
        const group = groups.nth(i);
        if (await group.isVisible()) await group.click();
      }

      const toolIds = await page.evaluate(() =>
        Array.from(document.querySelectorAll('[data-testid^="tool-btn-"]'))
          .map((el) => el.getAttribute('data-testid').replace('tool-btn-', ''))
      );
      await page.getByRole('button', { name: 'Close menu' }).click();

      expect(toolIds.length, `${role} was offered no screens at all`).toBeGreaterThan(0);

      for (const toolId of toolIds) {
        await page.goto(`/dashboard?tool=${toolId}`);
        await expect(page.getByTestId('app-layout')).toBeVisible();

        expect(await documentOverflow(page), `${role} / ${toolId}: page scrolls sideways`).toBeLessThanOrEqual(1);
        expect(await overhangingElements(page), `${role} / ${toolId}: content overhangs the screen edge`).toEqual([]);
      }
    } finally {
      await context.close();
    }
  });
}
