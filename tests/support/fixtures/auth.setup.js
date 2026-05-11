/**
 * Auth Setup — Playwright global setup
 *
 * Logs in as admin once and saves the browser storage state so all tests
 * can reuse the authenticated session without repeating the login flow.
 *
 * Run automatically as the "setup" project in playwright.config.js.
 */

const { test: setup, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const ADMIN_STATE_FILE = path.join(__dirname, '.auth', 'admin.json');

setup('authenticate as admin', async ({ page }) => {
  // Ensure the .auth directory exists
  const authDir = path.dirname(ADMIN_STATE_FILE);
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  const baseURL = process.env.BASE_URL || 'http://localhost:3000';
  const username = process.env.TEST_ADMIN_USERNAME || 'admin';
  const password = process.env.TEST_ADMIN_PASSWORD || 'admin123';

  await page.goto(`${baseURL}/login`);

  // Fill login form — using data-testid selectors (EduFlow convention)
  await page.getByTestId('login-username').fill(username);
  await page.getByTestId('login-password').fill(password);
  await page.getByTestId('login-submit').click();

  // Wait for successful redirect to dashboard
  await page.waitForURL('**/dashboard', { timeout: 30_000 });
  await expect(page.getByTestId('app-layout')).toBeVisible();

  // Persist storage state
  await page.context().storageState({ path: ADMIN_STATE_FILE });
  console.log(`[auth.setup] Admin session saved to ${ADMIN_STATE_FILE}`);
});
