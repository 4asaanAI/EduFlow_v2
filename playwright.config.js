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

    // ── Real phone and tablet profiles (Release 3, item E) ───────────────────
    //
    // WHAT WAS MISSING, and why it let a real report through. Until now the only
    // "mobile" project was Desktop Chrome with the window made narrow: no touch, no
    // device pixel ratio, a desktop user agent and `isMobile` false. That is a small
    // desktop, not a phone. It is why the owner's iPhone 15 Pro report of 2026-08-06
    // - "it opened already magnified, and tapping a box magnified it further" - was
    // not caught by a suite that was green at 390px wide.
    //
    // These two carry the things that were absent: touch, `isMobile`, a real device
    // pixel ratio (2.625 and 2), a mobile user agent, and the phone's actual viewport.
    //
    // BROWSER ENGINE, said plainly. Both run on Chromium, because WebKit is not
    // installed in this environment (see the disabled project below). So these prove
    // the LAYOUT and the touch behaviour on a real phone and tablet shape; they do
    // not prove Safari's engine. The zoom-on-focus rule that caused the owner's
    // report is asserted directly, by measuring computed font size, so it is caught
    // regardless of engine - which is the right way round anyway, because reading the
    // stylesheet was what hid it for a fortnight.
    //
    // Phone and tablet are the PRIMARY devices here; desktop is secondary.
    {
      name: 'phone-pixel',
      testMatch: /e2e\/(responsive|tables-on-a-phone)\.spec\.js/,
      use: {
        ...devices['Pixel 7'],
        browserName: 'chromium',
        channel: chromiumChannel,
        storageState: 'tests/support/fixtures/.auth/admin.json',
      },
      dependencies: ['setup'],
    },
    {
      name: 'tablet-ipad',
      testMatch: /e2e\/(responsive|tables-on-a-phone)\.spec\.js/,
      use: {
        ...devices['iPad (gen 7)'],
        // The iPad profile defaults to WebKit, which is not installed here. The
        // viewport, the touch and the 2x pixel ratio are what this project is for and
        // they all survive the swap; the engine difference is stated above rather
        // than left for somebody to discover.
        browserName: 'chromium',
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
