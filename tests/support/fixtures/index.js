/**
 * Fixture Index — EduFlow Playwright Test Fixtures
 *
 * Merges all custom fixtures using Playwright's `test.extend()` / `mergeTests()`.
 * Import `{ test, expect }` from this file in all e2e tests instead of
 * importing directly from `@playwright/test`.
 *
 * Usage:
 *   const { test, expect } = require('../support/fixtures');
 */

const { test: base, expect, mergeTests } = require('@playwright/test');
const { createApiFixture } = require('./api-fixture');

// ─── API Request Fixture ─────────────────────────────────────────────────────
const withApi = base.extend({
  /**
   * `apiRequest` — pre-configured APIRequestContext pointing at the backend.
   *
   * Usage in test:
   *   test('...', async ({ apiRequest }) => {
   *     const res = await apiRequest.get('/api/auth/me');
   *   });
   */
  apiRequest: async ({ playwright }, use) => {
    const apiURL = process.env.API_URL || 'http://localhost:8000';
    const context = await playwright.request.newContext({
      baseURL: apiURL,
      extraHTTPHeaders: {
        'Content-Type': 'application/json',
      },
    });
    await use(context);
    await context.dispose();
  },
});

// ─── Auth Fixture (already-authenticated page) ───────────────────────────────
const withAuth = withApi.extend({
  /**
   * `authedPage` — a page that already has the admin auth session loaded.
   * Uses the storage state saved by auth.setup.js.
   */
  authedPage: async ({ page }, use) => {
    await use(page);
  },
});

// Export the merged test object
const test = mergeTests(withAuth);

module.exports = { test, expect };
