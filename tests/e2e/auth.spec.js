/**
 * E2E Tests: Authentication — EduFlow
 *
 * Tests the login/logout flow and access control.
 *
 * Pattern: Given/When/Then (comments), data-testid selectors, factory data.
 *
 * NOTE: These tests do NOT use the shared auth session (auth.setup.js) because
 * they test the auth flow itself. They run without storageState.
 */

const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../support/page-objects/LoginPage');
const { buildCredentials } = require('../support/helpers/factories');
const { expectLoginPage } = require('../support/helpers/auth');

// Override project storageState for auth tests — no pre-auth session
test.use({ storageState: { cookies: [], origins: [] } });

test.describe('Authentication', () => {
  test.describe('Login', () => {
    test('should log in with valid admin credentials', async ({ page }) => {
      // Given: the login page is open
      const loginPage = new LoginPage(page);
      await loginPage.goto();
      await expect(loginPage.form).toBeVisible();

      // When: valid admin credentials are submitted
      const creds = buildCredentials('admin');
      await loginPage.loginAndWait(creds);

      // Then: user is redirected to the dashboard
      await expect(page).toHaveURL(/\/dashboard/);
    });

    test('should show error with invalid credentials', async ({ page }) => {
      // Given: the login page is open
      const loginPage = new LoginPage(page);
      await loginPage.goto();

      // When: invalid credentials are submitted
      await loginPage.login({ username: 'wronguser', password: 'wrongpass' });

      // Then: an error message is displayed, user stays on login page
      await expect(loginPage.errorMessage).toBeVisible();
      await expect(loginPage.errorMessage).toContainText(/invalid|incorrect|not found/i);
      await expect(page).toHaveURL(/\/login/);
    });

    test('should require both username and password', async ({ page }) => {
      // Given: the login page is open
      const loginPage = new LoginPage(page);
      await loginPage.goto();

      // When: form is submitted empty
      await loginPage.submitButton.click();

      // Then: form validation prevents submission (HTML5 or custom validation)
      await expect(page).toHaveURL(/\/login/);
    });
  });

  test.describe('Access Control', () => {
    test('should redirect unauthenticated users to login', async ({ page }) => {
      // Given: user is not logged in
      // When: they navigate directly to a protected route
      await page.goto('/dashboard');

      // Then: they are redirected to the login page
      await expectLoginPage(page, expect);
    });
  });
});
