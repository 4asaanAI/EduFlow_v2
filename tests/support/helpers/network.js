/**
 * Network Helpers — EduFlow E2E Tests
 *
 * Utilities for intercepting, mocking, and waiting for network requests
 * in Playwright tests.
 *
 * Pattern: Network-first — always wait for the real API response in tests
 * unless you explicitly need to mock it (error states, slow responses, etc.)
 */

/**
 * Wait for a specific API route to respond.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string|RegExp} urlPattern - URL pattern to match
 * @param {{ method?: string, timeout?: number }} options
 * @returns {Promise<import('@playwright/test').Response>}
 */
async function waitForApiResponse(page, urlPattern, options = {}) {
  const { method = 'GET', timeout = 15_000 } = options;
  return page.waitForResponse(
    (response) => {
      const urlMatches =
        typeof urlPattern === 'string'
          ? response.url().includes(urlPattern)
          : urlPattern.test(response.url());
      return urlMatches && response.request().method() === method;
    },
    { timeout }
  );
}

/**
 * Mock an API route to return a fixed response.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string|RegExp} urlPattern - URL pattern to intercept
 * @param {{ status?: number, body?: object, method?: string }} mockResponse
 */
async function mockApiRoute(page, urlPattern, mockResponse = {}) {
  const { status = 200, body = {}, method } = mockResponse;

  await page.route(urlPattern, (route) => {
    const request = route.request();
    if (method && request.method() !== method) {
      return route.continue();
    }
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
}

/**
 * Mock a network error for a route (simulates offline / server down).
 *
 * @param {import('@playwright/test').Page} page
 * @param {string|RegExp} urlPattern
 */
async function mockNetworkError(page, urlPattern) {
  await page.route(urlPattern, (route) => {
    route.abort('failed');
  });
}

/**
 * Intercept and capture all requests matching a pattern (for assertions).
 *
 * @param {import('@playwright/test').Page} page
 * @param {string|RegExp} urlPattern
 * @returns {{ requests: import('@playwright/test').Request[], stop: Function }}
 */
function captureRequests(page, urlPattern) {
  const requests = [];
  const handler = (request) => {
    const matches =
      typeof urlPattern === 'string'
        ? request.url().includes(urlPattern)
        : urlPattern.test(request.url());
    if (matches) requests.push(request);
  };
  page.on('request', handler);
  return {
    requests,
    stop: () => page.off('request', handler),
  };
}

module.exports = { waitForApiResponse, mockApiRoute, mockNetworkError, captureRequests };
