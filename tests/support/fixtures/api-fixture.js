/**
 * API Fixture Helper — EduFlow
 *
 * Provides a thin wrapper around Playwright's APIRequestContext for making
 * authenticated API requests in tests.
 *
 * Note: createApiFixture is a factory — call it with an auth token when you
 * need an authenticated context outside of the page-level fixture.
 */

/**
 * Login via API and return the JWT token.
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {{ username: string, password: string }} credentials
 * @returns {Promise<string>} JWT token
 */
async function loginViaApi(request, credentials = {}) {
  const username = credentials.username || process.env.TEST_ADMIN_USERNAME || 'admin';
  const password = credentials.password || process.env.TEST_ADMIN_PASSWORD || 'admin123';

  const response = await request.post('/api/auth/login', {
    data: { username, password },
  });

  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Login failed (${response.status()}): ${body}`);
  }

  const data = await response.json();
  return data.access_token;
}

/**
 * Create an authenticated API request factory.
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {string} token - JWT bearer token
 * @returns {{ get, post, put, patch, del }} Authenticated request helpers
 */
function createAuthenticatedApi(request, token) {
  const headers = { Authorization: `Bearer ${token}` };

  return {
    get: (path, options = {}) =>
      request.get(path, { ...options, headers: { ...headers, ...options.headers } }),

    post: (path, data, options = {}) =>
      request.post(path, { data, ...options, headers: { ...headers, ...options.headers } }),

    put: (path, data, options = {}) =>
      request.put(path, { data, ...options, headers: { ...headers, ...options.headers } }),

    patch: (path, data, options = {}) =>
      request.patch(path, { data, ...options, headers: { ...headers, ...options.headers } }),

    del: (path, options = {}) =>
      request.delete(path, { ...options, headers: { ...headers, ...options.headers } }),
  };
}

module.exports = { loginViaApi, createAuthenticatedApi };
