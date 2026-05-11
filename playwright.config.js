// @ts-check
/**
 * Playwright Configuration — EduFlow E2E Tests
 *
 * Framework: Playwright (JS, not TS — project uses plain JS)
 * Stack: React 19 + FastAPI fullstack
 * Env var: BASE_URL (fallback: http://localhost:3000)
 */

const { defineConfig, devices } = require('@playwright/test');

/** @type {import('@playwright/test').PlaywrightTestConfig} */
const config = defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,

  // ─── Timeouts ──────────────────────────────────────────────────────────────
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    baseURL: process.env.BASE_URL || 'http://localhost:3000',

    // ─── Artifacts — retain on failure ──────────────────────────────────────
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  // ─── Reporters ─────────────────────────────────────────────────────────────
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
    ['list'],
  ],

  // ─── Output directory ──────────────────────────────────────────────────────
  outputDir: 'test-results',

  // ─── Browser projects ──────────────────────────────────────────────────────
  projects: [
    // Setup project — authenticate once, reuse session
    {
      name: 'setup',
      testMatch: /.*\.setup\.js/,
    },

    // Chromium (primary)
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'tests/support/fixtures/.auth/admin.json',
      },
      dependencies: ['setup'],
    },

    // Firefox
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        storageState: 'tests/support/fixtures/.auth/admin.json',
      },
      dependencies: ['setup'],
    },

    // WebKit / Safari
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        storageState: 'tests/support/fixtures/.auth/admin.json',
      },
      dependencies: ['setup'],
    },
  ],

  // ─── Dev server (optional local auto-start) ─────────────────────────────
  // Uncomment to auto-start the frontend when running locally.
  // webServer: {
  //   command: 'yarn --cwd frontend start',
  //   url: 'http://localhost:3000',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120_000,
  // },
});

module.exports = config;
