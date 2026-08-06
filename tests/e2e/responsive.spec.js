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

/**
 * No field may be smaller than 16px on a phone.
 *
 * Owner report, 2026-08-06 (iPhone 15 Pro): the platform opened already magnified,
 * with the menu and profile picture cut off the screen edges, and tapping any entry
 * box magnified it further — neither one asked for. Both are the SAME defect. Safari
 * force-zooms the page whenever a field under 16px takes focus, and it never zooms
 * back out, so one tap left the whole site stuck magnified for the rest of the visit.
 *
 * The 16px floor was already written in `index.css` and could not take effect: this
 * codebase styles with React inline `style={{}}`, and an inline style outranks any
 * plain stylesheet rule, so thirteen shared style objects at 12-15px silently won.
 *
 * COMPUTED size is what is asserted, deliberately. Reading the CSS file would have
 * reported the floor as present and correct throughout the period it was being
 * overridden — the exact reason this went unnoticed.
 */
async function undersizedFields(page) {
  return page.evaluate(() => {
    const SKIP = new Set(['checkbox', 'radio', 'range', 'submit', 'button', 'reset', 'hidden', 'color', 'file']);
    const offenders = [];
    for (const el of document.querySelectorAll('input, select, textarea')) {
      if (el.tagName === 'INPUT' && SKIP.has((el.type || 'text').toLowerCase())) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;   // not on screen
      const size = parseFloat(window.getComputedStyle(el).fontSize);
      if (size < 16) {
        const id = el.getAttribute('data-testid') || el.getAttribute('name') || el.getAttribute('placeholder') || '(unnamed)';
        offenders.push(`${el.tagName.toLowerCase()}[${id}] ${size}px`);
      }
    }
    return offenders.slice(0, 8);
  });
}

test('the page never forbids the user from zooming themselves', async ({ page }) => {
  // The usual one-line "fix" for zoom-on-focus is `maximum-scale=1, user-scalable=no`.
  // It is banned here on two grounds: Abhimanyu asked that pinch-zoom keep working
  // when the user chooses it, and taking zoom away from people who need it to read is
  // an accessibility failure. The zoom is stopped by removing its cause instead.
  await page.goto('/login');
  const viewport = await page.locator('meta[name="viewport"]').getAttribute('content');
  expect(viewport, 'viewport meta tag is missing').toBeTruthy();
  expect(viewport, 'the user must not be blocked from zooming').not.toMatch(/user-scalable\s*=\s*(no|0)/i);
  expect(viewport, 'a maximum-scale of 1 blocks the user from zooming').not.toMatch(/maximum-scale\s*=\s*1(\.0)?\b/i);
});

test('no field on the sign-in screen triggers an iOS zoom', async ({ page }) => {
  // Checked separately because it is the one screen every user meets before any
  // session exists, and the role sweep below signs in first.
  await page.setViewportSize(PHONE);
  await page.goto('/login');
  expect(await undersizedFields(page), 'sign-in fields under 16px will zoom on an iPhone').toEqual([]);
});

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
        expect(await undersizedFields(page), `${role} / ${toolId}: fields under 16px will zoom the page on an iPhone`).toEqual([]);
      }
    } finally {
      await context.close();
    }
  });
}
