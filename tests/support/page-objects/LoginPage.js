/**
 * Page Object: LoginPage — EduFlow
 *
 * Encapsulates all interactions with the /login page.
 * Use this in tests instead of raw locators for maintainability.
 */

class LoginPage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    this.page = page;
    // Locators
    this.usernameInput = page.getByTestId('login-username');
    this.passwordInput = page.getByTestId('login-password');
    this.submitButton = page.getByTestId('login-submit');
    this.errorMessage = page.getByTestId('login-error');
    this.form = page.getByTestId('login-form');
  }

  async goto() {
    await this.page.goto('/login');
  }

  /**
   * Fill and submit the login form.
   * @param {{ username: string, password: string }} credentials
   */
  async login({ username, password }) {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  /**
   * Login and wait for redirect to dashboard.
   * @param {{ username: string, password: string }} credentials
   */
  async loginAndWait({ username, password }) {
    await this.login({ username, password });
    await this.page.waitForURL('**/dashboard', { timeout: 30_000 });
  }

  async getErrorText() {
    return this.errorMessage.textContent();
  }
}

module.exports = { LoginPage };
