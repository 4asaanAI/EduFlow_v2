// @ts-check
/**
 * Playwright Configuration — EduFlow E2E Tests
 *
 * Framework: Playwright (JS, not TS — project uses plain JS)
 * Stack: React 19 + FastAPI fullstack
 * Env var: BASE_URL (fallback: http://localhost:3000)
 */

const { defineConfig, devices } = require('@playwright/test');
const isWindows = process.platform === 'win32';
const chromiumChannel = process.env.PLAYWRIGHT_CHANNEL || undefined;

/** @type {import('@playwright/test').PlaywrightTestConfig} */
const config = defineConfig({
  testDir: './tests',
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
      testMatch: /support\/fixtures\/auth\.setup\.js/,
      use: { channel: chromiumChannel },
    },

    // Chromium (primary)
    {
      name: 'chromium',
      testMatch: /e2e\/.*\.spec\.js/,
      testIgnore: /e2e\/responsive\.spec\.js/,
      use: {
        ...devices['Desktop Chrome'],
        channel: chromiumChannel,
        storageState: 'tests/support/fixtures/.auth/admin.json',
      },
      dependencies: ['setup'],
    },

    // Firefox
    {
      name: 'firefox',
      testMatch: /e2e\/.*\.spec\.js/,
      testIgnore: /e2e\/responsive\.spec\.js/,
      use: {
        ...devices['Desktop Firefox'],
        storageState: 'tests/support/fixtures/.auth/admin.json',
      },
      dependencies: ['setup'],
    },

    // Six-width layout contract. Kept in its own project so normal functional
    // scenarios are not multiplied across every phone/tablet width.
    {
      name: 'responsive-chromium',
      testMatch: /e2e\/responsive\.spec\.js/,
      use: {
        ...devices['Desktop Chrome'],
        channel: chromiumChannel,
        storageState: 'tests/support/fixtures/.auth/admin.json',
      },
      dependencies: ['setup'],
    },

    // WebKit / Safari — disabled: not supported on macOS 13
    // Re-enable on macOS 14+ with: npx playwright install webkit
    // {
    //   name: 'webkit',
    //   use: {
    //     ...devices['Desktop Safari'],
    //     storageState: 'tests/support/fixtures/.auth/admin.json',
    //   },
    //   dependencies: ['setup'],
    // },
  ],

  // ─── Dev server (optional local auto-start) ─────────────────────────────
  webServer: [
    {
      command: isWindows ? 'python tests/support/e2e_backend.py' : 'python3 tests/support/e2e_backend.py',
      url: 'http://localhost:8000/api/auth/refresh',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: isWindows
        ? 'cd frontend && set PORT=3000&& set BROWSER=none&& set REACT_APP_BACKEND_URL=http://localhost:8000&& npm start'
        : 'cd frontend && PORT=3000 BROWSER=none REACT_APP_BACKEND_URL=http://localhost:8000 npm start',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});

module.exports = config;
