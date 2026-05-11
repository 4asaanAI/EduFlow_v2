# EduFlow Test Suite

This document covers setup, running, and architecture of the EduFlow test suite.

**Stack:** React 19 (plain JS) + FastAPI Python  
**E2E Framework:** Playwright (JavaScript)  
**Backend Framework:** pytest (Python)  
**Generated:** 2026-05-12

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Directory Structure](#directory-structure)
3. [Environment Setup](#environment-setup)
4. [Running Tests](#running-tests)
5. [Architecture Overview](#architecture-overview)
6. [Writing Tests](#writing-tests)
7. [Best Practices](#best-practices)
8. [CI Integration](#ci-integration)

---

## Quick Start

### Install dependencies

**Playwright (E2E):**

```bash
# From the project root
npm install -D @playwright/test
npx playwright install --with-deps
# Or via Makefile:
make playwright-install
```

**pytest (Backend):**

```bash
cd backend
pip install pytest pytest-asyncio httpx pytest-cov
# All other deps already in requirements.txt
```

### Set up environment

```bash
cp .env.test.example .env.test
# Edit .env.test with your local values
```

### Run tests

```bash
# E2E tests
make test-e2e

# Backend tests
make test-backend

# All tests
make test
```

---

## Directory Structure

```
tests/
├── README.md                         # This file
│
├── e2e/                              # Playwright E2E tests
│   ├── auth.spec.js                  # Login / logout / access control
│   ├── chat.spec.js                  # Chat interface — core flow
│   └── students.spec.js              # Student management flows
│
├── support/
│   ├── fixtures/
│   │   ├── index.js                  # Merged fixture export (import from here)
│   │   ├── auth.setup.js             # Global auth setup (saves session)
│   │   ├── api-fixture.js            # API request helpers + auth factory
│   │   └── .auth/                    # Auth state files (gitignored)
│   │       └── admin.json            # Saved admin session (generated)
│   │
│   ├── helpers/
│   │   ├── factories.js              # Test data factories (student, staff, etc.)
│   │   ├── auth.js                   # UI login/logout helpers
│   │   └── network.js                # Network intercept / mock utilities
│   │
│   └── page-objects/
│       ├── LoginPage.js              # Login page POM
│       └── ChatPage.js               # Chat interface POM
│
└── backend/                          # pytest backend tests
    ├── conftest.py                   # Shared fixtures (client, auth_headers, etc.)
    ├── unit/
    │   └── test_validators.py        # Pure function / Pydantic validator tests
    ├── integration/
    │   └── test_health.py            # App startup, CORS, health checks
    └── api/
        ├── test_auth.py              # POST /api/auth/login, GET /api/auth/me
        └── test_students.py          # CRUD /api/students

playwright.config.js                  # Playwright config (project root)
pytest.ini                            # pytest config (project root)
.coveragerc                           # Coverage settings
.env.test.example                     # Template for test environment vars
Makefile                              # Convenience test commands
```

---

## Environment Setup

Copy `.env.test.example` to `.env.test` and configure:

| Variable | Description | Default |
|---|---|---|
| `BASE_URL` | Frontend URL for Playwright | `http://localhost:3000` |
| `API_URL` | Backend URL for API requests | `http://localhost:8000` |
| `REACT_APP_BACKEND_URL` | Backend URL as seen by React | `http://localhost:8000` |
| `TEST_ADMIN_USERNAME` | Admin login username | `admin` |
| `TEST_ADMIN_PASSWORD` | Admin login password | `admin123` |
| `MONGODB_URL` | MongoDB connection (pytest) | `mongodb://localhost:27017/eduflow_test` |
| `JWT_SECRET` | JWT secret for test tokens | `test-jwt-secret-...` |
| `ENVIRONMENT` | Enables API docs, test mode | `test` |

**Important:** `.env.test` is gitignored. Never commit real credentials.

---

## Running Tests

### E2E Tests (Playwright)

```bash
# Headless (default — CI mode)
make test-e2e
# or:
npx playwright test --config=playwright.config.js

# Headed (see the browser)
make test-e2e-headed

# Debug mode (Playwright Inspector — step through tests)
make test-e2e-debug

# UI mode (interactive test runner)
make test-e2e-ui

# Specific file
npx playwright test tests/e2e/auth.spec.js

# Specific test by name
npx playwright test -g "should log in with valid admin credentials"

# Single browser
npx playwright test --project=chromium

# View last HTML report
make playwright-report
```

### Backend Tests (pytest)

```bash
# All backend tests
make test-backend

# Unit tests only (no external deps, fastest)
make test-backend-unit

# API tests (requires running backend + seeded DB)
make test-backend-api

# Integration tests
make test-backend-integration

# With coverage
make test-backend-cov

# Specific file
cd backend && python -m pytest ../tests/backend/api/test_auth.py -v

# Specific test
cd backend && python -m pytest ../tests/backend/api/test_auth.py::TestLogin::test_login_with_valid_credentials -v

# By marker
cd backend && python -m pytest ../tests/backend -m "unit" -v
```

---

## Architecture Overview

### Playwright (E2E)

```
playwright.config.js
├── testDir: ./tests/e2e
├── projects:
│   ├── setup (runs auth.setup.js — saves admin session)
│   ├── chromium (depends on setup)
│   ├── firefox (depends on setup)
│   └── webkit (depends on setup)
├── Timeouts: action 15s, navigation 30s, test 60s
└── Artifacts: trace + screenshot + video on failure
```

**Key patterns:**

- **Auth session reuse:** `auth.setup.js` logs in once per run and saves `storageState` to `tests/support/fixtures/.auth/admin.json`. All tests in the `chromium/firefox/webkit` projects load this state automatically — no repeated logins.
- **Page Objects:** Use classes in `tests/support/page-objects/` to encapsulate locators. Always prefer `data-testid` selectors.
- **Custom fixtures:** Import `{ test, expect }` from `tests/support/fixtures/index.js` (not from `@playwright/test`) to get `apiRequest` and `authedPage` fixtures.
- **Network helpers:** Use `waitForApiResponse()` in `network.js` for network-first assertions.

### pytest (Backend)

```
pytest.ini
├── testpaths: tests/backend
├── markers: unit, integration, api, slow, auth
└── asyncio_mode: auto

tests/backend/conftest.py
├── client          — FastAPI TestClient (sync, session-scoped)
├── async_client    — httpx AsyncClient (async tests)
├── auth_token      — JWT from POST /api/auth/login (session-scoped)
├── auth_headers    — { Authorization: Bearer <token> } (session-scoped)
├── student_data    — Factory: minimal student payload
└── staff_data      — Factory: minimal staff payload
```

**Test categories:**

| Category | Location | DB needed? | Speed |
|---|---|---|---|
| `unit` | `tests/backend/unit/` | No | Fast (< 1s) |
| `integration` | `tests/backend/integration/` | App only | Medium |
| `api` | `tests/backend/api/` | Yes (seeded) | Slower |

---

## Writing Tests

### E2E Test Template

```javascript
// tests/e2e/my-feature.spec.js
const { test, expect } = require('../support/fixtures');
const { MyPage } = require('../support/page-objects/MyPage');
const { buildStudent } = require('../support/helpers/factories');

test.describe('My Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/my-route');
  });

  test('should do something', async ({ page }) => {
    // Given: ...
    const myPage = new MyPage(page);
    const data = buildStudent();

    // When: ...
    await myPage.doSomething(data);

    // Then: ...
    await expect(myPage.result).toBeVisible();
    await expect(myPage.result).toContainText(data.name);
  });
});
```

### Backend Test Template

```python
# tests/backend/api/test_my_endpoint.py
import pytest

class TestMyEndpoint:
    """GET /api/my-endpoint"""

    def test_happy_path(self, client, auth_headers):
        """Given valid request, should return 200 with expected data."""
        response = client.get("/api/my-endpoint", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data

    def test_unauthenticated(self, client):
        """Without token, should return 401."""
        response = client.get("/api/my-endpoint")
        assert response.status_code == 401
```

---

## Best Practices

### Selectors (E2E)

Always prefer `data-testid` attributes — they're stable and communicate intent:

```javascript
// Good
page.getByTestId('login-submit')
page.getByTestId('student-name')

// Avoid — brittle
page.locator('.btn.primary')
page.locator('button:nth-child(2)')
```

Add `data-testid` to React components when writing new UI:
```jsx
<button data-testid="login-submit" onClick={onSubmit}>Login</button>
```

### Test Isolation

- Each test should be independent — do not rely on other tests' side effects.
- Use `test.beforeEach` / `test.afterEach` for setup/cleanup.
- Auth state is shared per run (via `auth.setup.js`) but individual tests must not modify it.
- For tests that modify data (POST/PUT/DELETE), clean up in `afterEach` or use unique identifiers from factories.

### Factory Usage

Always use factory functions for test data — never hardcode:

```javascript
const { buildStudent, buildCredentials } = require('../support/helpers/factories');

// Good
const student = buildStudent({ class_name: 'Class 10' });

// Avoid — hardcoded, brittle
const student = { name: 'John', class_name: 'Class 5', ... };
```

### Network-First Pattern

Wait for real API responses before asserting on UI:

```javascript
const { waitForApiResponse } = require('../support/helpers/network');

const [apiRes] = await Promise.all([
  waitForApiResponse(page, '/api/students', { method: 'GET' }),
  page.getByTestId('load-students').click(),
]);
expect(apiRes.status()).toBe(200);
```

---

## CI Integration

### GitHub Actions (Playwright)

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 24
      - name: Install Playwright
        run: npx playwright install --with-deps
      - name: Run E2E tests
        env:
          BASE_URL: ${{ secrets.TEST_BASE_URL }}
          API_URL: ${{ secrets.TEST_API_URL }}
          TEST_ADMIN_USERNAME: ${{ secrets.TEST_ADMIN_USERNAME }}
          TEST_ADMIN_PASSWORD: ${{ secrets.TEST_ADMIN_PASSWORD }}
        run: npx playwright test --config=playwright.config.js
      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: playwright-report/
```

### GitHub Actions (pytest)

```yaml
# .github/workflows/backend-test.yml
name: Backend Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r backend/requirements.txt pytest pytest-asyncio httpx pytest-cov
      - name: Run unit tests (no DB)
        run: python -m pytest tests/backend/unit -v -m unit
      - name: Run integration tests
        env:
          MONGODB_URL: ${{ secrets.TEST_MONGODB_URL }}
          JWT_SECRET: ${{ secrets.TEST_JWT_SECRET }}
          TEST_ADMIN_USERNAME: ${{ secrets.TEST_ADMIN_USERNAME }}
          TEST_ADMIN_PASSWORD: ${{ secrets.TEST_ADMIN_PASSWORD }}
        run: python -m pytest tests/backend -v --ignore=tests/backend/unit
```

---

## Next Steps

1. **Install Playwright:** `npx playwright install --with-deps`
2. **Install pytest deps:** `pip install pytest pytest-asyncio httpx pytest-cov`
3. **Copy env file:** `cp .env.test.example .env.test` and fill in credentials
4. **Start backend:** `cd backend && uvicorn server:app --reload`
5. **Start frontend:** `cd frontend && yarn start`
6. **Run E2E:** `make test-e2e`
7. **Run backend tests:** `make test-backend`
8. **Add `data-testid` attributes** to React components as you add new UI features
9. **Add page objects** in `tests/support/page-objects/` for new pages
10. **Add API tests** in `tests/backend/api/` for new endpoints
