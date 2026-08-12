/**
 * Every table on the platform, walked on a real phone and a real tablet.
 *
 * Release 3, item E. Phone and tablet are the PRIMARY devices here; desktop is
 * secondary. This file runs under the `phone-pixel` and `tablet-ipad` projects in
 * `playwright.config.js`, which carry touch, `isMobile` and a real device pixel
 * ratio - none of which the old resized-Chromium project had, and their absence is
 * why the owner's iPhone report of 2026-08-06 was not caught by a green suite.
 *
 * WHAT IS CHECKED ON EVERY SCREEN THAT HAS A TABLE:
 *
 *  1. The page does not scroll sideways, and no card overhangs the screen edge. A
 *     table may scroll sideways INSIDE its own wrapper - that is the design - but the
 *     page around it may not, or the right-hand edge is simply lost.
 *  2. No entry box is under 16px. Safari force-zooms the page when a smaller field
 *     takes focus and never zooms back out, so one tap leaves the whole site
 *     magnified. That is exactly what the owner reported, twice, as two faults.
 *  3. Anything a thumb must hit is at least 40px tall. A 24px control on a phone is
 *     a control somebody mis-hits, and mis-hitting a row on a fee screen opens the
 *     wrong family.
 *  4. THE COUNT IS ON SCREEN. Every table this release touched says how many rows it
 *     holds, and how many of them are drawn or shown. A phone is where a truncated
 *     list is least visible, so it is where saying the number matters most.
 */

const { test, expect } = require('../support/fixtures');

const E2E_PASSWORD = 'admin123';

// Every screen the owner and the principal can open that carries a table. Read off
// the menu at run time rather than hard-coded, for the same reason the role sweep in
// responsive.spec.js does it: a hard-coded list stops covering new screens the day
// somebody adds one, and does it silently.
async function signInAs(page, username) {
  await page.goto('/login');
  await page.getByTestId('login-username').fill(username);
  await page.getByTestId('login-password').fill(E2E_PASSWORD);
  await page.getByTestId('login-submit').click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  await expect(page.getByTestId('app-layout')).toBeVisible();
}

async function toolIdsOnMenu(page) {
  // A PHONE has a hamburger; a TABLET is wide enough that the menu is already open
  // and there is no hamburger to press. Assuming one made every tablet run fail on a
  // missing button, which said nothing at all about the tablet layout it was there
  // to check. Both shapes are handled rather than one being called the normal one.
  const hamburger = page.getByRole('button', { name: 'Open menu' });
  const collapsed = await hamburger.count() > 0 && await hamburger.isVisible();
  if (collapsed) await hamburger.click();
  await expect(page.getByTestId('sidebar')).toBeVisible();

  // Teachers and students keep every screen inside a collapsed group, so the tools
  // are not in the page until each group is opened.
  const groups = page.locator('[data-testid^="tool-group-"]');
  for (let i = 0; i < await groups.count(); i += 1) {
    const group = groups.nth(i);
    if (await group.isVisible()) await group.click();
  }
  const ids = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-testid^="tool-btn-"]'))
      .map((el) => el.getAttribute('data-testid').replace('tool-btn-', '')));
  if (collapsed) await page.getByRole('button', { name: 'Close menu' }).click();
  return ids;
}

/** Content sticking out past the right edge of the app's own main area. */
async function overhangingElements(page) {
  return page.evaluate(() => {
    const main = document.querySelector('.app-main-content');
    if (!main) return [];
    const limit = main.getBoundingClientRect().right + 1;
    const offenders = [];
    for (const el of main.querySelectorAll('*')) {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      // A region MEANT to scroll sideways, and everything inside it, is allowed to
      // be wider than the screen. That is how a wide table stays readable on a phone.
      let cursor = el;
      let inScroller = false;
      while (cursor && cursor !== main) {
        const ox = window.getComputedStyle(cursor).overflowX;
        if (ox === 'auto' || ox === 'scroll') { inScroller = true; break; }
        cursor = cursor.parentElement;
      }
      if (inScroller) continue;
      if (rect.right > limit) {
        offenders.push(`${el.tagName.toLowerCase()}.${el.className || '(no class)'} right=${Math.round(rect.right)}`);
      }
    }
    return offenders.slice(0, 5);
  });
}

/** Fields small enough that iOS will magnify the page when they are tapped. */
async function undersizedFields(page) {
  return page.evaluate(() => {
    const SKIP = new Set(['checkbox', 'radio', 'range', 'submit', 'button', 'reset', 'hidden', 'color', 'file']);
    const offenders = [];
    for (const el of document.querySelectorAll('input, select, textarea')) {
      if (el.tagName === 'INPUT' && SKIP.has((el.type || 'text').toLowerCase())) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      const size = parseFloat(window.getComputedStyle(el).fontSize);
      if (size < 16) {
        const id = el.getAttribute('data-testid') || el.getAttribute('name') || '(unnamed)';
        offenders.push(`${el.tagName.toLowerCase()}[${id}] ${size}px`);
      }
    }
    return offenders.slice(0, 8);
  });
}

/** Controls too small for a thumb. 40px is the floor these screens are built to. */
async function undersizedTapTargets(page) {
  return page.evaluate(() => {
    const offenders = [];
    const wanted = 'button, select, input:not([type=hidden]), [role="button"], a[href]';
    for (const el of document.querySelectorAll(`.app-main-content ${wanted}`)) {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      // An inline link inside a sentence is text, not a tap target with its own box.
      if (el.tagName === 'A' && el.closest('p, span')) continue;
      // A tick box is square and is sized by width and height. It is checked against
      // its own floor below rather than against the 40px one, which would only ever
      // be met by stretching it into an oval.
      const type = (el.getAttribute('type') || '').toLowerCase();
      if (type === 'checkbox' || type === 'radio' || type === 'range') {
        // A slider is DRAGGED rather than tapped, so it needs the full 40px: a
        // finger landing beside a thin track moves nothing at all. A tick box only
        // needs to be square and big enough to hit.
        const floor = type === 'range' ? 40 : 20;
        if (rect.height < floor) {
          offenders.push(`${type} ${Math.round(rect.height)}px - too small for a finger`);
        }
        continue;
      }
      if (rect.height < 40) {
        const id = el.getAttribute('data-testid') || (el.textContent || '').trim().slice(0, 24) || '(unnamed)';
        offenders.push(`${el.tagName.toLowerCase()}[${id}] ${Math.round(rect.height)}px tall`);
      }
    }
    return offenders.slice(0, 8);
  });
}


for (const role of ['owner', 'principal', 'accountant', 'management', 'teacher']) {
  test(`every table ${role} can open behaves on this device`, async ({ browser }) => {
    test.setTimeout(300_000);
    // A fresh context WITHOUT the saved owner session, or every role would silently
    // be checked as the owner and the sweep would prove nothing.
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();
    try {
      await signInAs(page, role);
      const toolIds = await toolIdsOnMenu(page);
      expect(toolIds.length, `${role} was offered no screens at all`).toBeGreaterThan(0);

      let screensSeen = 0;
      const faults = [];
      for (const toolId of toolIds) {
        await page.goto(`/dashboard?tool=${toolId}`);
        await expect(page.getByTestId('app-layout')).toBeVisible();
        // Give the rows a moment to arrive; a screen checked before it has drawn
        // passes for the wrong reason.
        await page.waitForTimeout(400);
        screensSeen += 1;

        // COLLECTED, not asserted one at a time. Failing on the first screen would
        // hide every screen after it, so a sweep meant to find everything would report
        // one thing per run and take a day to work through.
        const sideways = await page.evaluate(() =>
          document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (sideways > 1) faults.push(`${toolId}: the page scrolls sideways by ${sideways}px`);
        for (const f of await overhangingElements(page)) faults.push(`${toolId}: overhangs - ${f}`);
        for (const f of await undersizedFields(page)) faults.push(`${toolId}: field under 16px - ${f}`);
        for (const f of await undersizedTapTargets(page)) faults.push(`${toolId}: too small to tap - ${f}`);
      }

      expect(faults, `${role}: ${faults.length} problems on this device`).toEqual([]);

      // A sweep that quietly checked nothing would pass, which is this release's
      // defining fault applied to its own test suite.
      expect(screensSeen, `${role}: no screen was checked at all`).toBeGreaterThan(0);
    } finally {
      await context.close();
    }
  });
}

// The two checks that need REAL ROWS - "it says how many it is showing" and "a wide
// table scrolls inside itself" - are not here, and that is deliberate rather than an
// omission. The stand-in backend this suite runs against serves fixed empty lists, so
// both would be passing on the harness and not on the product, which is a worse
// answer than not asking. They are asserted against real row data in the unit suite
// instead: `RowsDrawnAsYouScroll.test.js` pins the drawn count, and
// `ResponsiveLayoutContract.test.js` pins the table's own sideways scroll.
