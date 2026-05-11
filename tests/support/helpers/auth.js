/**
 * Auth Helpers — EduFlow E2E Tests
 *
 * Shared helper functions for authentication flows in Playwright tests.
 * Use these when you need to log in/out within a test (outside of the
 * global auth.setup session).
 */

/**
 * Perform a full login via the UI.
 *
 * @param {import('@playwright/test').Page} page
 * @param {{ username: string, password: string }} credentials
 */
async function loginViaUI(page, { username, password }) {
  const baseURL = process.env.BASE_URL || 'http://localhost:3000';
  await page.goto(`${baseURL}/login`);
  await page.getByTestId('login-username').fill(username);
  await page.getByTestId('login-password').fill(password);
  await page.getByTestId('login-submit').click();
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
}

/**
 * Log out via the UI.
 *
 * @param {import('@playwright/test').Page} page
 */
async function logoutViaUI(page) {
  // Open the user menu and click logout
  await page.getByTestId('user-menu-trigger').click();
  await page.getByTestId('logout-button').click();
  await page.waitForURL('**/login', { timeout: 15_000 });
}

/**
 * Check that the current page is the login page (unauthenticated).
 *
 * @param {import('@playwright/test').Page} page
 * @param {import('@playwright/test').Expect} expect
 */
async function expectLoginPage(page, expect) {
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByTestId('login-form')).toBeVisible();
}

module.exports = { loginViaUI, logoutViaUI, expectLoginPage };
